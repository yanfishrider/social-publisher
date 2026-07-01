"""
浏览器管理器 — 负责浏览器的启动、复用和关闭
"""
from playwright.sync_api import sync_playwright, BrowserContext
from pathlib import Path


class BrowserManager:
    """管理 Playwright 浏览器实例"""

    def __init__(self, user_data_dir: str, headless: bool = False,
                 viewport_width: int = 1920, viewport_height: int = 1080):
        self.user_data_dir = Path(user_data_dir)
        self.headless = headless
        self.viewport = {"width": viewport_width, "height": viewport_height}
        self._playwright = None
        self._context: BrowserContext | None = None

    def start(self) -> BrowserContext:
        """启动浏览器并返回持久化上下文"""
        self.user_data_dir.mkdir(parents=True, exist_ok=True)

        self._playwright = sync_playwright().start()
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.user_data_dir),
            headless=self.headless,
            viewport=self.viewport,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            geolocation={"latitude": 22.558, "longitude": 113.463},
            permissions=["geolocation"],
        )
        print(f"✅ 浏览器已启动 (profile: {self.user_data_dir})")
        return self._context

    def close(self):
        """关闭浏览器"""
        if self._context:
            self._context.close()
            print("✅ 浏览器已关闭")
        if self._playwright:
            self._playwright.stop()
