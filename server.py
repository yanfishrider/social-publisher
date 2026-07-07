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

app = FastAPI(title="社交发布工具")

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
    return Path("templates/index.html").read_text(encoding="utf-8")


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

    if len(content) > 500:
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

        # 标题截断
        title_used = title[:max_title] if len(title) > max_title else title

        # 内容改写
        if len(content) > 500:
            send("📝 内容过长，自动改写...", platform=platform)
            if platform in ("xiaohongshu", "douyin"):
                rewritten = rewriter(content, title_used)
            else:
                rewritten = rewriter(content, title_used)
            body = rewritten["body"]
        else:
            body = content

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

        worker_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "publish_worker.py")

        send("🔗 启动发布子进程...", platform=platform)
        proc = subprocess.Popen(
            [sys.executable, worker_path, json.dumps(worker_config, ensure_ascii=False)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            cwd=os.path.dirname(os.path.abspath(__file__)),
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
