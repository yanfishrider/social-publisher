"""
社交发布 Web 界面 — FastAPI 服务
Playwright 通过独立子进程运行，避免 sync API 与 asyncio 冲突。
"""
import sys
import os
import json
import queue
import asyncio
import threading
import subprocess
import traceback
from pathlib import Path

from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import HTMLResponse, StreamingResponse

from image_utils import compress_image
from content_rewriter import rewrite_for_xhs, rewrite_for_article
from rate_limiter import can_publish, record as record_publish
from safety_gate import check_acknowledgment

app = FastAPI(title="社交发布工具")

check_acknowledgment()

# PyInstaller 打包后的资源路径
_BASE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))

# 输出目录：exe 同目录下的 output/ 文件夹
if getattr(sys, 'frozen', False):
    OUTPUT_DIR = Path(sys.executable).parent / "output"
else:
    OUTPUT_DIR = Path(__file__).parent / "output"


def _resolve_path(relative: str) -> Path:
    """解析资源文件路径，兼容开发环境和 PyInstaller 打包"""
    return _BASE_DIR / relative


PUBLISHERS = {
    "weibo":      ("weibo",      rewrite_for_article, 32),
    "xiaohongshu":("xiaohongshu",rewrite_for_xhs,     20),
    "toutiao":    ("toutiao",    rewrite_for_article, 30),
    "baijiahao":  ("baijiahao",  rewrite_for_article, 64),
    "bilibili":   ("bilibili",   rewrite_for_article, 30),
    "douyin":     ("douyin",     rewrite_for_xhs,     20),
}

# ── 页面 ──

@app.get("/", response_class=HTMLResponse)
async def index():
    return _resolve_path("templates/index.html").read_text(encoding="utf-8")


# ── 预览 ──

@app.post("/preview")
async def preview(
    platform: str = Form(...),
    title: str = Form(...),
    content_file: UploadFile | None = None,
    content_text: str = Form(""),
):
    content = content_text
    if content_file:
        content = (await content_file.read()).decode("utf-8")

    if not content:
        return {"error": "没有内容", "body": ""}

    _, rewriter, _ = PUBLISHERS.get(platform, PUBLISHERS["weibo"])

    # 小红书 1000 字才触发改写，其余平台 500 字
    xhs_threshold = 1000 if platform == "xiaohongshu" else 500

    if len(content) > xhs_threshold:
        if platform in ("xiaohongshu", "douyin"):
            result = rewriter(content, title)
        else:
            result = rewriter(content)
        return {"title": result.get("title", title), "body": result["body"]}
    else:
        return {"title": title, "body": content}


# ── 发布 (SSE 流式日志) ──

@app.post("/publish")
async def publish(
    platforms: str = Form(...),
    title: str = Form(...),
    content_file: UploadFile | None = None,
    content_text: str = Form(""),
    cover_image: UploadFile | None = None,
    tags: str = Form(""),
    auto_submit: str = Form("1"),
):
    content = content_text
    if content_file:
        content = (await content_file.read()).decode("utf-8")

    cover_path = None
    if cover_image:
        os.makedirs("uploads", exist_ok=True)
        cover_path = os.path.abspath(f"uploads/{cover_image.filename}")
        with open(cover_path, "wb") as f:
            f.write(await cover_image.read())

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    manual = (auto_submit != "1")
    platform_list = [p.strip() for p in platforms.split(",") if p.strip()]

    msg_queue: queue.Queue = queue.Queue()

    def send(msg: str, error: bool = False, done: bool = False, platform: str = ""):
        msg_queue.put({"msg": msg, "error": error, "done": done, "platform": platform})

    # 在后台线程顺序处理所有平台，每个平台用独立子进程
    def run_publish():
        try:
            for platform in platform_list:
                try:
                    _publish_one(platform)
                except Exception as e:
                    send(f"❌ {platform} 异常: {e}", error=True, platform=platform)
                    traceback.print_exc()
        finally:
            send("", done=True)

    def _publish_one(platform: str):
        send(f"── 开始发布到 {platform} ──", platform=platform)

        _, rewriter, max_title = PUBLISHERS.get(platform, PUBLISHERS["weibo"])

        title_used = title

        # 所有内容都格式化（去 Markdown 符号），小红书/抖音额外截断
        threshold = 1000 if platform == "xiaohongshu" else 500
        if platform in ("xiaohongshu", "douyin") and len(content) > threshold:
            rewritten = rewriter(content, title_used)
            body = rewritten["body"]
            title_used = rewritten.get("title", title_used)
        else:
            # 百家号/头条号等：全文格式化
            rewritten = rewrite_for_article(content)
            body = rewritten["body"]
            title_used = rewritten.get("title", title_used) or title_used

        send(f"📄 标题: {title_used} | 正文: {len(body)}字", platform=platform)

        # 频率控制
        ok, reason = can_publish(platform)
        if not ok:
            send(f"⏭️ 跳过: {reason}", platform=platform)
            return

        # 封面压缩
        final_cover = cover_path
        if final_cover:
            send(f"🖼️ 处理封面: {final_cover}", platform=platform)
            compressed = compress_image(final_cover, max_size_mb=5)
            if compressed:
                final_cover = compressed
                send(f"  ✅ 封面就绪", platform=platform)

        # 构建子进程参数
        worker_config = {
            "platform": platform,
            "title": title_used,
            "body": body,
            "cover": final_cover,
            "tags": tag_list,
            "manual": manual,
        }

        send("🔗 启动发布子进程...", platform=platform)

        # 兼容 PyInstaller 打包和开发环境
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包：调用自身 exe 的 --worker 模式
            cmd = [sys.executable, "--worker", json.dumps(worker_config, ensure_ascii=False)]
            cwd = os.path.dirname(sys.executable)
        else:
            # 开发环境：调用 publish_worker.py
            worker_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "publish_worker.py")
            cmd = [sys.executable, worker_path, json.dumps(worker_config, ensure_ascii=False)]
            cwd = os.path.dirname(os.path.abspath(__file__))

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            cwd=cwd,
        )

        # 逐行读取子进程输出
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                send(**msg)
                # 手动模式：worker 已填完，跳出循环继续下一个平台
                if manual and msg.get("done"):
                    break
            except json.JSONDecodeError:
                send(f"  {line}", platform=platform)

        if manual:
            # 手动模式：worker 填完即断 CDP 退出，不阻塞
            pass
        else:
            # 自动模式：读 stderr 后等进程结束
            stderr_output = proc.stderr.read()
            if stderr_output.strip():
                for line in stderr_output.strip().split("\n"):
                    line = line.strip()
                    if line:
                        send(f"  [stderr] {line}", platform=platform)
            proc.wait()
            record_publish(platform, title_used)

    thread = threading.Thread(target=run_publish, daemon=True)
    thread.start()

    # SSE 流式返回
    async def event_stream():
        while True:
            try:
                msg = msg_queue.get(timeout=0.5)
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                if msg["done"]:
                    break
            except queue.Empty:
                if not thread.is_alive():
                    break
                await asyncio.sleep(0.1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")




# ── 文件转换 ──

@app.post("/api/convert/pdf")
async def convert_pdf(file: UploadFile):
    """上传 PDF → 转换为 MD，输出到 output/ 目录"""
    import pdf_to_markdown

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename).stem
    input_path = OUTPUT_DIR / f"_{safe_name}.pdf"
    output_path = OUTPUT_DIR / f"{safe_name}.md"

    content = await file.read()
    input_path.write_bytes(content)

    try:
        info = pdf_to_markdown.diagnose(input_path)
        if not info["has_text"]:
            input_path.unlink(missing_ok=True)
            return {
                "ok": False,
                "error": "PDF 为扫描件/图片型，无法提取文字。请使用 OCR 工具处理。",
                "info": {k: v for k, v in info.items() if k != "text_per_page"},
            }

        import pymupdf4llm
        md_text = pymupdf4llm.to_markdown(str(input_path))
        output_path.write_text(md_text, encoding="utf-8")
        input_path.unlink(missing_ok=True)

        return {
            "ok": True,
            "output": str(output_path),
            "filename": output_path.name,
            "size_kb": round(output_path.stat().st_size / 1024, 1),
            "pages": info["pages"],
        }
    except Exception as e:
        input_path.unlink(missing_ok=True)
        return {"ok": False, "error": str(e)}


@app.post("/api/convert/docx")
async def convert_docx(file: UploadFile):
    """上传 DOCX → 转换为 MD，输出到 output/ 目录"""
    from docx_to_markdown import convert as docx_convert

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename).stem
    input_path = OUTPUT_DIR / f"_{safe_name}.docx"
    output_path = OUTPUT_DIR / f"{safe_name}.md"

    content = await file.read()
    input_path.write_bytes(content)

    try:
        docx_convert(input_path, output_path)
        input_path.unlink(missing_ok=True)
        return {
            "ok": True,
            "output": str(output_path),
            "filename": output_path.name,
            "size_kb": round(output_path.stat().st_size / 1024, 1),
        }
    except Exception as e:
        input_path.unlink(missing_ok=True)
        return {"ok": False, "error": str(e)}


# ── 平台登录 ──

@app.post("/api/login")
async def login_platform():
    """打开 CDP 浏览器（连接 Edge），用户自行前往各平台登录"""
    login_config = {"action": "login", "url": "about:blank"}

    if getattr(sys, 'frozen', False):
        cmd = [sys.executable, "--login", json.dumps(login_config, ensure_ascii=False)]
        cwd = os.path.dirname(sys.executable)
    else:
        worker_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "publish_worker.py")
        cmd = [sys.executable, worker_path, json.dumps(login_config, ensure_ascii=False)]
        cwd = os.path.dirname(os.path.abspath(__file__))

    subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        cwd=cwd,
    )

    return {"ok": True, "msg": "Edge 浏览器已打开，请自行前往各平台登录"}


# ── 频率统计 ──

@app.get("/stats")
async def stats():
    """查看各平台发布统计"""
    from rate_limiter import get_stats
    return get_stats()


# ── 启动 ──

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)
