"""
发布工作进程 — 独立进程运行 Playwright Sync API，不受 FastAPI asyncio 影响。
由 server.py 通过 subprocess 调用。
用法: uv run python publish_worker.py '<json_config>'
"""
import sys
import json
import traceback


def main():
    config = json.loads(sys.argv[1])

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
        print(json.dumps({"msg": "🔗 连接 Edge 浏览器...", "platform": platform}))
        sys.stdout.flush()
        pub = pub_cls(auto_submit=not manual)
        pub.start()

        print(json.dumps({"msg": "🌐 打开发布页面...", "platform": platform}))
        sys.stdout.flush()
        success = pub.publish(title, body, cover, tags)

        if success:
            if manual:
                print(json.dumps({
                    "msg": "⏸️  请在浏览器中手动点击发布按钮",
                    "done": False,
                    "platform": platform,
                }))
                print(json.dumps({"msg": "", "done": True}))
                sys.stdout.flush()
                # 手动模式：断开 CDP（保留 Edge 页面），不阻塞
            else:
                print(json.dumps({
                    "msg": "🎉 发布成功！",
                    "platform": platform,
                }))
        else:
            print(json.dumps({
                "error": True,
                "msg": "❌ 填充失败",
                "platform": platform,
            }))

    except Exception as e:
        print(json.dumps({
            "error": True,
            "msg": f"❌ {e}",
            "platform": platform,
        }))
        traceback.print_exc(file=sys.stderr)
    finally:
        if pub:
            if manual:
                # 手动模式：只断开 CDP，不关闭 Edge 页面
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


if __name__ == "__main__":
    main()
