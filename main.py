"""
社交平台发布工具 — CLI 入口
"""
import argparse
import sys

from config import PublishConfig, load_config_from_args
from browser_manager import BrowserManager
from image_utils import compress_image
from platforms.xiaohongshu import XhsPublisher
from platforms.baijiahao import BaijiahaoPublisher
from platforms.toutiao import ToutiaoPublisher
from content_rewriter import rewrite_for_xhs, rewrite_for_article


def cmd_publish(args):
    platform = args.platform
    config = load_config_from_args(args)

    if not config.title:
        print("❌ 缺少 --title"); sys.exit(1)
    if not config.content_loaded:
        print("❌ 缺少 --content-file 或 --content-text"); sys.exit(1)

    use_edge = getattr(args, 'use_edge', False)

    if platform == "xiaohongshu":
        # 自动改写：内容 >500 字时提取精华
        content = config.content_loaded
        xhs_tags = list(config.tags)
        xhs_title = config.short_title or config.title[:20]

        if config.content_file and len(content) > 500:
            print("📝 内容过长，自动生成小红书风格文案...")
            rewritten = rewrite_for_xhs(content, xhs_title)
            xhs_title = rewritten["title"]
            content = rewritten["body"]
            # 合并标签
            for t in rewritten["tags"]:
                if t not in xhs_tags:
                    xhs_tags.append(t)
            print(f"   标题: {xhs_title}")
            print(f"   正文: {len(content)}字 | 标签: {xhs_tags}")

        if not config.cover_image:
            print("❌ 缺少 --cover-image"); sys.exit(1)

        cover_path = compress_image(config.cover_image, max_size_mb=5)
        if not cover_path:
            print("❌ 封面图处理失败"); sys.exit(1)

        if use_edge:
            pub = XhsPublisher()
            pub.start()
            success = pub.publish(xhs_title, content, cover_path, xhs_tags)
            pub.stop()
        else:
            browser = BrowserManager(user_data_dir=config.browser_data_dir, headless=config.headless)
            ctx = browser.start()
            try:
                pub = XhsPublisher()
                pub.context = ctx
                success = pub.publish(xhs_title, content, cover_path, xhs_tags)
            finally:
                browser.close()

        disp_title = xhs_title

    elif platform == "baijiahao":
        if not config.cover_image:
            print("❌ 百家号封面图为必填，缺少 --cover-image"); sys.exit(1)

        content = config.content_loaded
        bjh_tags = list(config.tags)

        if config.content_file and len(content) > 2000:
            print("📝 Markdown 过长，自动转为纯文本段落...")
            rewritten = rewrite_for_article(content)
            content = rewritten["body"]
            for t in rewritten["tags"]:
                if t not in bjh_tags:
                    bjh_tags.append(t)
            print(f"   正文: {len(content)}字 | 标签: {bjh_tags}")

        if use_edge:
            pub = BaijiahaoPublisher()
            pub.start()
            success = pub.publish(
                title=config.title,
                content=content,
                cover_image=config.cover_image,
                tags=bjh_tags,
            )
            pub.stop()
        else:
            browser = BrowserManager(user_data_dir=config.browser_data_dir, headless=config.headless)
            ctx = browser.start()
            try:
                pub = BaijiahaoPublisher()
                pub.context = ctx
                success = pub.publish(
                    title=config.title,
                    content=content,
                    cover_image=config.cover_image,
                    tags=bjh_tags,
                )
            finally:
                browser.close()

        disp_title = config.title

    elif platform == "toutiao":
        content = config.content_loaded
        tt_tags = list(config.tags)

        if config.content_file and len(content) > 2000:
            print("📝 Markdown 过长，自动转为纯文本段落...")
            rewritten = rewrite_for_article(content)
            content = rewritten["body"]
            for t in rewritten["tags"]:
                if t not in tt_tags:
                    tt_tags.append(t)
            print(f"   正文: {len(content)}字 | 标签: {tt_tags}")

        if use_edge:
            pub = ToutiaoPublisher()
            pub.start()
            success = pub.publish(
                title=config.title,
                content=content,
                cover_image=config.cover_image,
                tags=tt_tags,
            )
            pub.stop()
        else:
            browser = BrowserManager(user_data_dir=config.browser_data_dir, headless=config.headless)
            ctx = browser.start()
            try:
                pub = ToutiaoPublisher()
                pub.context = ctx
                success = pub.publish(
                    title=config.title,
                    content=content,
                    cover_image=config.cover_image,
                    tags=tt_tags,
                )
            finally:
                browser.close()

        disp_title = config.title

    else:
        print(f"❌ 未知平台: {platform}"); sys.exit(1)

    if success:
        print(f"\n{'='*60}\n🎉 发布完成！\n   标题: {disp_title}\n{'='*60}")
    else:
        print("\n❌ 发布失败")
        sys.exit(1)


def cmd_login(args):
    print(f"🌐 打开 {args.platform} 登录页...")
    browser = BrowserManager(user_data_dir=args.browser_data_dir, headless=False)
    ctx = browser.start()
    page = ctx.new_page()

    if args.platform == "xiaohongshu":
        page.goto("https://creator.xiaohongshu.com/", timeout=30000)
    elif args.platform == "baijiahao":
        page.goto("https://baijiahao.baidu.com/", timeout=30000)
    elif args.platform == "toutiao":
        page.goto("https://mp.toutiao.com/", timeout=30000)

    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(3000)
    input("登录完成后按 Enter 关闭...")
    page.close()
    browser.close()
    print("✅ 已保存")


def main():
    parser = argparse.ArgumentParser(description="多平台社交媒体自动发布工具")
    sub = parser.add_subparsers(dest="command")

    pub = sub.add_parser("publish")
    pub.add_argument("platform", choices=["xiaohongshu", "baijiahao", "toutiao"])
    pub.add_argument("--title", required=True)
    pub.add_argument("--short-title")
    pub.add_argument("--cover-image")
    pub.add_argument("--content-file")
    pub.add_argument("--content-text")
    pub.add_argument("--tags")
    pub.add_argument("--category", help="文章分类（百家号等平台使用）")
    pub.add_argument("--browser-data-dir", default="./chromium-browser-data")
    pub.add_argument("--headless", action="store_true")
    pub.add_argument("--use-edge", action="store_true", help="连接真实 Edge 浏览器（需先启动: msedge --remote-debugging-port=9222）")

    login = sub.add_parser("login")
    login.add_argument("platform", choices=["xiaohongshu", "baijiahao", "toutiao"])
    login.add_argument("--browser-data-dir", default="./chromium-browser-data")

    args = parser.parse_args()

    if args.command == "publish":
        cmd_publish(args)
    elif args.command == "login":
        cmd_login(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
