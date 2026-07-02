"""
小红书图文发布器 — 通过 CDP 连接真实 Edge 浏览器
不会被检测为自动化浏览器
"""
from playwright.sync_api import sync_playwright, BrowserContext, Page


class XhsPublisher:
    PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?source=official"
    CDP_URL = "http://localhost:9222"

    def __init__(self):
        self._playwright = None
        self._browser = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    def start(self):
        """连接真实 Edge 浏览器"""
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.connect_over_cdp(self.CDP_URL)
        self.context = self._browser.contexts[0]
        # 劫持 attachShadow，强制改成 open 模式
        self.context.add_init_script("""
            const orig = Element.prototype.attachShadow;
            Element.prototype.attachShadow = function(init) {
                return orig.call(this, { ...init, mode: 'open' });
            };
        """)
        print("✅ 已连接 Edge + Shadow DOM 劫持")

    def stop(self):
        if self._playwright:
            self._playwright.stop()

    def publish(self, title: str, description: str, cover_image: str,
                tags: list[str] | None = None) -> bool:
        if self.context is None:
            raise RuntimeError("未启动浏览器，先调 start() 或设置 context")
        tags = tags or []
        try:
            self.page = self.context.new_page()
            print("🌐 打开小红书...")
            self.page.goto(self.PUBLISH_URL, timeout=30000)
            self.page.wait_for_load_state("domcontentloaded")
            self.page.wait_for_timeout(3000)

            if "login" in self.page.url:
                print("⚠️ 未登录")
                return False
            print("✅ 已登录")

            self._switch_tab()
            self._upload(cover_image)
            self._wait_editor()
            self._set_title(title)
            self._set_body(description, tags)
            self._publish()

            print("🎉 发布成功！")
            return True
        except Exception as e:
            print(f"❌ {e}")
            import traceback; traceback.print_exc()
            return False
        finally:
            if self.page:
                self.page.wait_for_timeout(3000)
                self.page.close()

    def _switch_tab(self):
        print("📷 切标签...")
        for i in range(self.page.locator(".creator-tab:has-text('上传图文')").count()):
            try:
                self.page.locator(".creator-tab:has-text('上传图文')").nth(i).click(force=True, timeout=3000)
                self.page.wait_for_timeout(2000)
                print("  ✅")
                return
            except: continue

    def _upload(self, path):
        print(f"🖼️ 上传: {path}")
        self.page.locator("input[type='file']").first.set_input_files(path)
        self.page.wait_for_timeout(3000)
        print("  ✅")

    def _wait_editor(self):
        print("⏳ 等编辑器...")
        self.page.wait_for_selector("[placeholder*='标题']", timeout=15000)
        self.page.wait_for_timeout(1000)
        print("  ✅")

    def _set_title(self, title):
        if len(title) > 20:
            # 智能截断：在空格/标点处断，不截半个词
            cut = title[:20]
            # 回退到最后一个合适的断点
            for sep in [" — ", " - ", " ", "，", "。", "、"]:
                idx = cut.rfind(sep)
                if idx > 10:  # 至少保留10个字
                    cut = cut[:idx]
                    break
            title = cut
        print(f"📝 标题: {title}")
        self.page.locator("[placeholder*='标题']").first.fill(title)
        self.page.wait_for_timeout(500)

    def _set_body(self, text, tags):
        print(f"📄 正文 ({len(text)}字)...")
        editors = self.page.locator("[contenteditable='true'], textarea")
        desc = editors.nth(1) if editors.count() >= 2 else editors.first
        desc.type(text, delay=20)
        self.page.wait_for_timeout(500)
        if tags:
            print(f"🏷️ 标签: {tags}")
            for t in tags:
                desc.type(f" #{t}", delay=15)
                self.page.wait_for_timeout(800)
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(300)

    def _publish(self):
        print("🚀 发布...")
        # Shadow DOM 已被劫持为 open，直接选择器
        btn = self.page.locator("button.ce-btn.bg-red")
        if btn.count() > 0:
            btn.first.click()
            print("  ✅ button.ce-btn.bg-red 点击")
        else:
            btn = self.page.get_by_role("button", name="发布")
            if btn.count() > 0:
                btn.first.click()
                print("  ✅ get_by_role 点击")
            else:
                self.page.keyboard.press("Control+Enter")
                print("  ✅ Ctrl+Enter")
        self.page.locator("text=发布成功").wait_for(timeout=60000)
        print("✅ 发布成功！")
