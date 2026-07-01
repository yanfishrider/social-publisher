"""
配置加载模块 — 从 .env 文件和命令行参数加载配置
"""
import os
from pathlib import Path
from dataclasses import dataclass, field

# 尝试加载 .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class PublishConfig:
    """一次发布任务的所有配置"""
    # === 内容 ===
    title: str                              # 文章标题（必填）
    content_file: str | None = None         # Markdown 文件路径
    content_text: str | None = None         # 或直接提供文本内容

    # === 封面图 ===
    cover_image: str | None = None          # 封面图路径

    # === 短标题（图文平台用，≤20字） ===
    short_title: str | None = None

    # === 标签 ===
    tags: list[str] = field(default_factory=list)

    # === 通用 ===
    browser_data_dir: str = "./chromium-browser-data"
    headless: bool = False
    viewport_width: int = 1920
    viewport_height: int = 1080

    # === 文本内容（从文件加载后填充） ===
    content_loaded: str | None = field(default=None, repr=False)


def load_config_from_args(args) -> PublishConfig:
    """从 argparse 结果构造 PublishConfig"""
    # 解析标签
    tags = []
    if args.tags:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    # 从文件加载内容
    content_text = None
    content_loaded = None
    content_file = args.content_file

    if content_file:
        with open(content_file, "r", encoding="utf-8") as f:
            content_loaded = f.read()

    if args.content_text:
        content_text = args.content_text
        content_loaded = args.content_text

    return PublishConfig(
        title=args.title,
        content_file=content_file,
        content_text=content_text,
        content_loaded=content_loaded,
        cover_image=args.cover_image,
        short_title=args.short_title,
        tags=tags,
        browser_data_dir=args.browser_data_dir,
        headless=args.headless,
    )
