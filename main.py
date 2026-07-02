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
from platforms.bilibili import BilibiliPublisher
from platforms.douyin import DouyinPublisher
from platforms.weibo import WeiboPublisher
from content_rewriter import rewrite_for_xhs, rewrite_for_article


def _publish_xhs(config: PublishConfig, use_edge: bool):
    """发布小红书"""
    content = config.content_loaded
    xhs_tags = list(config.tags)
    xhs_title = config.short_title or config.title

    if config.content_file and len(content) > 500:
        print("📝 内容过长，自动生成小红书风格文案...")
        rewritten = rewrite_for_xhs(content, xhs_title)
        xhs_title = rewritten["title"]
        content = rewritten["body"]
        for t in rewritten["tags"]:
            if t not in xhs_tags:
                xhs_tags.append(t)
        print(f"   标题: {xhs_title}")
        print(f"   正文: {len(content)}字 | 标签: {xhs_tags}")

    if not config.cover_image:
        print("❌ 缺少 --cover-image"); return False

    cover_path = compress_image(config.cover_image, max_size_mb=5)
    if not cover_path:
        print("❌ 封面图处理失败"); return False

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

    return success, xhs_title


def _publish_bjh(config: PublishConfig, use_edge: bool):
    """发布百家号"""
    if not config.cover_image:
        print("❌ 百家号封面图为必填"); return False, config.title

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
        success = pub.publish(config.title, content, config.cover_image, bjh_tags)
        pub.stop()
    else:
        browser = BrowserManager(user_data_dir=config.browser_data_dir, headless=config.headless)
        ctx = browser.start()
        try:
            pub = BaijiahaoPublisher()
            pub.context = ctx
            success = pub.publish(config.title, content, config.cover_image, bjh_tags)
        finally:
            browser.close()

    return success, config.title


def _publish_tt(config: PublishConfig, use_edge: bool):
    """发布头条号"""
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
        success = pub.publish(config.title, content, config.cover_image, tt_tags)
        pub.stop()
    else:
        browser = BrowserManager(user_data_dir=config.browser_data_dir, headless=config.headless)
        ctx = browser.start()
        try:
            pub = ToutiaoPublisher()
            pub.context = ctx
            success = pub.publish(config.title, content, config.cover_image, tt_tags)
        finally:
            browser.close()

    return success, config.title


def _publish_bili(config: PublishConfig, use_edge: bool):
    """发布 B 站专栏"""
    content = config.content_loaded
    bili_tags = list(config.tags)

    if config.content_file and len(content) > 2000:
        print("📝 Markdown 过长，自动转为纯文本段落...")
        rewritten = rewrite_for_article(content)
        content = rewritten["body"]
        for t in rewritten["tags"]:
            if t not in bili_tags:
                bili_tags.append(t)
        print(f"   正文: {len(content)}字 | 标签: {bili_tags}")

    if use_edge:
        pub = BilibiliPublisher()
        pub.start()
        success = pub.publish(config.title, content, bili_tags)
        pub.stop()
    else:
        browser = BrowserManager(user_data_dir=config.browser_data_dir, headless=config.headless)
        ctx = browser.start()
        try:
            pub = BilibiliPublisher()
            pub.context = ctx
            success = pub.publish(config.title, content, bili_tags)
        finally:
            browser.close()

    return success, config.title


def _publish_dy(config: PublishConfig, use_edge: bool):
    """发布抖音图文"""
    if not config.cover_image:
        print("❌ 抖音图文需要 --cover-image"); return False, config.title

    content = config.content_loaded
    dy_tags = list(config.tags)

    # 抖音正文限制 ~1000字，内容过长时自动精简
    if len(content) > 800:
        print("📝 内容过长，自动精简...")
        rewritten = rewrite_for_xhs(content, config.title)
        content = rewritten["body"]
        for t in rewritten["tags"]:
            if t not in dy_tags:
                dy_tags.append(t)
        print(f"   正文: {len(content)}字 | 标签: {dy_tags}")

    if use_edge:
        pub = DouyinPublisher()
        pub.start()
        success = pub.publish(config.title, content, config.cover_image, dy_tags)
        pub.stop()
    else:
        browser = BrowserManager(user_data_dir=config.browser_data_dir, headless=config.headless)
        ctx = browser.start()
        try:
            pub = DouyinPublisher()
            pub.context = ctx
            success = pub.publish(config.title, content, config.cover_image, dy_tags)
        finally:
            browser.close()

    return success, config.title


def _publish_wb(config: PublishConfig, use_edge: bool):
    """发布微博头条文章 — ProseMirror 支持 Markdown，直接传原始内容"""
    content = config.content_loaded

    if use_edge:
        pub = WeiboPublisher()
        pub.start()
        success = pub.publish(config.title, content, config.cover_image, config.tags)
        pub.stop()
    else:
        browser = BrowserManager(user_data_dir=config.browser_data_dir, headless=config.headless)
        ctx = browser.start()
        try:
            pub = WeiboPublisher()
            pub.context = ctx
            success = pub.publish(config.title, content, config.cover_image, config.tags)
        finally:
            browser.close()

    return success, config.title


def cmd_publish(args):
    platform = args.platform
    config = load_config_from_args(args)

    if not config.title:
        print("❌ 缺少 --title"); sys.exit(1)
    if not config.content_loaded:
        print("❌ 缺少 --content-file 或 --content-text"); sys.exit(1)

    use_edge = getattr(args, 'use_edge', False)

    platforms = [platform]
    if platform == "all":
        platforms = ["xiaohongshu", "baijiahao", "toutiao", "bilibili", "douyin", "weibo"]

    results = []
    for p in platforms:
        print(f"\n{'='*60}")
        print(f"📤 发布到 {p}")
        print(f"{'='*60}")

        if p == "xiaohongshu":
            ok, title = _publish_xhs(config, use_edge)
        elif p == "baijiahao":
            ok, title = _publish_bjh(config, use_edge)
        elif p == "toutiao":
            ok, title = _publish_tt(config, use_edge)
        elif p == "bilibili":
            ok, title = _publish_bili(config, use_edge)
        elif p == "douyin":
            ok, title = _publish_dy(config, use_edge)
        elif p == "weibo":
            ok, title = _publish_wb(config, use_edge)
        else:
            print(f"❌ 未知平台: {p}"); sys.exit(1)

        tag = "✅" if ok else "❌"
        results.append(f"  {tag} {p}: {title}")

    print(f"\n{'='*60}")
    print("📊 发布汇总")
    print(f"{'='*60}")
    for r in results:
        print(r)

    if not any("✅" in r for r in results):
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
    elif args.platform == "bilibili":
        page.goto("https://member.bilibili.com/platform/upload/text/new-edit", timeout=30000)
    elif args.platform == "douyin":
        page.goto("https://creator.douyin.com/creator-micro/content/upload", timeout=30000)
    elif args.platform == "weibo":
        page.goto("https://weibo.com/", timeout=30000)

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
    pub.add_argument("platform", choices=["xiaohongshu", "baijiahao", "toutiao", "bilibili", "douyin", "weibo", "all"])
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
    login.add_argument("platform", choices=["xiaohongshu", "baijiahao", "toutiao", "bilibili", "douyin", "weibo"])
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
