"""
社交发布 Web 界面 — FastAPI 服务
启动: uv run uvicorn server:app --reload --port 8080
"""
import sys
import io
import os
import json
import queue
import asyncio
import threading
import traceback
from pathlib import Path

from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import HTMLResponse, StreamingResponse

# ── 复用现有模块 ──
from config import PublishConfig
from image_utils import compress_image
from content_rewriter import rewrite_for_xhs, rewrite_for_article
from platforms.weibo import WeiboPublisher
from platforms.xiaohongshu import XhsPublisher
from platforms.toutiao import ToutiaoPublisher
from platforms.baijiahao import BaijiahaoPublisher
from platforms.bilibili import BilibiliPublisher
from platforms.douyin import DouyinPublisher

app = FastAPI(title="社交发布工具")

PUBLISHERS = {
    "weibo":      (WeiboPublisher,      rewrite_for_article, 32),
    "xiaohongshu":(XhsPublisher,        rewrite_for_xhs,     20),
    "toutiao":    (ToutiaoPublisher,    rewrite_for_article, 30),
    "baijiahao":  (BaijiahaoPublisher,  rewrite_for_article, 64),
    "bilibili":   (BilibiliPublisher,   rewrite_for_article, 30),
    "douyin":     (DouyinPublisher,     rewrite_for_xhs,     20),
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
    platform: str = Form(...),
    title: str = Form(...),
    content_file: UploadFile | None = None,
    content_text: str = Form(""),
    cover_image: UploadFile | None = None,
    tags: str = Form(""),
):
    # 保存上传文件到临时目录
    content = content_text
    if content_file:
        content = (await content_file.read()).decode("utf-8")

    cover_path = None
    if cover_image:
        os.makedirs("uploads", exist_ok=True)
        cover_path = f"uploads/{cover_image.filename}"
        with open(cover_path, "wb") as f:
            f.write(await cover_image.read())

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    msg_queue: queue.Queue = queue.Queue()

    def send(msg: str, error: bool = False, done: bool = False):
        msg_queue.put({"msg": msg, "error": error, "done": done})

    # 在后台线程执行发布（捕获 stdout）
    def run_publish():
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            pub_cls, rewriter, max_title = PUBLISHERS.get(platform, PUBLISHERS["weibo"])

            # 标题截断
            if len(title) > max_title:
                title_used = title[:max_title]
            else:
                title_used = title

            # 内容改写
            if len(content) > 500:
                send("📝 内容过长，自动改写...")
                if platform in ("xiaohongshu", "douyin"):
                    rewritten = rewriter(content, title_used)
                else:
                    rewritten = rewriter(content)
                body = rewritten["body"]
            else:
                body = content

            send(f"📄 标题: {title_used} | 正文: {len(body)}字")

            # 封面压缩
            final_cover = cover_path
            if final_cover:
                send(f"🖼️ 处理封面: {final_cover}")
                compressed = compress_image(final_cover, max_size_mb=5)
                if compressed:
                    final_cover = compressed
                    send(f"  ✅ 封面就绪")

            # 启动发布器
            send("🔗 连接 Edge 浏览器...")
            pub = pub_cls()
            pub.start()

            try:
                send("🌐 打开发布页面...")
                success = pub.publish(title_used, body, final_cover, tag_list)

                # 同时输出 publish 里面的 print 日志
                stdout_output = sys.stdout.getvalue()
                if stdout_output.strip():
                    for line in stdout_output.strip().split("\n"):
                        line = line.strip()
                        if line:
                            send(f"  {line}")

                if success:
                    send("🎉 发布成功！", done=True)
                else:
                    send(f"❌ 发布失败，请检查 Edge 浏览器状态", error=True, done=True)
            finally:
                pub.stop()

        except Exception as e:
            send(f"❌ {e}", error=True, done=True)
            traceback.print_exc()
        finally:
            sys.stdout = old_stdout

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


# ── 启动 ──

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)
