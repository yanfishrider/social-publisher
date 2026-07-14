"""
启动器 — PyInstaller 打包入口
双模式：
  1. 默认：启动 Edge 调试模式 + Web 窗口应用
  2. --worker <json>：执行发布任务（由 server.py 子进程调用）
  3. --login <json>：打开 CDP 浏览器（由 server.py 子进程调用）
"""
import sys
import os
import json
import subprocess
import socket
import time
import threading
import traceback
from pathlib import Path

# Windows 控制台 UTF-8 编码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _find_edge():
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for p in candidates:
        if Path(p).exists():
            return p
    return None


# Edge 独立 user data 目录（不跟日常 Edge 冲突）
if getattr(sys, 'frozen', False):
    EDGE_DATA = Path(sys.executable).parent / "edge-data"
else:
    EDGE_DATA = Path(__file__).parent / "edge-data"


def _check_port(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            return False


def _start_edge_debug():
    """启动 Edge 调试模式（独立 user-data-dir，不跟日常 Edge 冲突）"""
    if _check_port(9222):
        print("Edge 调试端口 9222 已就绪")
        return

    edge = _find_edge()
    if not edge:
        print("未找到 Edge 浏览器")
        sys.exit(1)

    EDGE_DATA.mkdir(parents=True, exist_ok=True)
    print(f"启动 Edge (data: {EDGE_DATA})")

    subprocess.Popen(
        [edge,
         f"--remote-debugging-port=9222",
         f"--user-data-dir={EDGE_DATA}",
         "--no-first-run",
         "--no-default-browser-check"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for _ in range(20):
        time.sleep(1)
        if _check_port(9222):
            print("Edge 调试端口就绪")
            return
    print("Edge 调试端口启动超时")


# ── 默认模式：桌面窗口应用 ──

def run_server():
    _start_edge_debug()

    import uvicorn
    from server import app

    port = 8083
    for alt in (8083, 8084, 8085, 8086):
        if not _check_port(alt):
            port = alt
            break
        print(f"端口 {alt} 已被占用")

    url = f"http://127.0.0.1:{port}"

    server_started = threading.Event()

    def serve():
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        server = uvicorn.Server(config)
        server_started.set()
        server.run()

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    server_started.wait()

    import webview
    window = webview.create_window(
        title="社交发布工具",
        url=url,
        width=900,
        height=750,
        resizable=True,
        min_size=(700, 550),
    )
    webview.start()


# ── 登录模式 ──

def run_login(config_json: str):
    from patchright.sync_api import sync_playwright

    config = json.loads(config_json)
    url = config.get("url", "about:blank")

    pw = None
    browser = None
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.new_page()
        page.goto(url, timeout=10000, wait_until="domcontentloaded")

        print(json.dumps({
            "ok": True,
            "msg": "浏览器已打开，请自行前往各平台登录。",
        }))
        sys.stdout.flush()

        while True:
            try:
                page.title()
                time.sleep(2)
            except Exception:
                break

    except Exception as e:
        print(json.dumps({"ok": False, "error": f"启动失败: {e}"}))
        sys.stdout.flush()
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        if pw:
            try:
                pw.stop()
            except Exception:
                pass


# ── Worker 模式 ──

def run_worker(config_json: str):
    config = json.loads(config_json)

    platform = config["platform"]
    title = config["title"]
    body = config["body"]
    cover = config.get("cover")
    tags = config.get("tags", [])
    manual = config.get("manual", False)

    from platforms.weibo import WeiboPublisher
    from platforms.xiaohongshu import XhsPublisher
    from platforms.toutiao import ToutiaoPublisher
    from platforms.baijiahao import BaijiahaoPublisher
    from platforms.bilibili import BilibiliPublisher
    from platforms.douyin import DouyinPublisher

    PUBLISHERS = {
        "weibo": WeiboPublisher,
        "xiaohongshu": XhsPublisher,
        "toutiao": ToutiaoPublisher,
        "baijiahao": BaijiahaoPublisher,
        "bilibili": BilibiliPublisher,
        "douyin": DouyinPublisher,
    }

    pub_cls = PUBLISHERS.get(platform)
    if not pub_cls:
        print(json.dumps({"error": True, "msg": f"未知平台: {platform}"}))
        return

    pub = None
    try:
        print(json.dumps({"msg": "连接 Edge...", "platform": platform}))
        sys.stdout.flush()
        pub = pub_cls(auto_submit=not manual)
        pub.start()

        print(json.dumps({"msg": "打开发布页面...", "platform": platform}))
        sys.stdout.flush()
        success = pub.publish(title, body, cover, tags)

        if success:
            if manual:
                print(json.dumps({
                    "msg": "请在浏览器中手动点击发布按钮",
                    "done": False,
                    "platform": platform,
                }))
                print(json.dumps({"msg": "", "done": True}))
                sys.stdout.flush()
            else:
                print(json.dumps({
                    "msg": "发布成功！",
                    "platform": platform,
                }))
        else:
            print(json.dumps({
                "error": True,
                "msg": "填充失败",
                "platform": platform,
            }))

    except Exception as e:
        print(json.dumps({
            "error": True,
            "msg": f"错误: {e}",
            "platform": platform,
        }))
        traceback.print_exc(file=sys.stderr)
    finally:
        if pub:
            if manual:
                if pub._browser:
                    try:
                        pub._browser.close()
                    except Exception:
                        pass
                if pub._playwright:
                    try:
                        pub._playwright.stop()
                    except Exception:
                        pass
            else:
                pub.stop()

    sys.stdout.flush()


# ── 入口 ──

if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--worker":
        run_worker(sys.argv[2])
    elif len(sys.argv) >= 3 and sys.argv[1] == "--login":
        run_login(sys.argv[2])
    else:
        run_server()
