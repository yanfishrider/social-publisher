"""
小红书图文发布器 — 通过 CDP 连接真实 Edge 浏览器
不会被检测为自动化浏览器
"""
from patchright.sync_api import sync_playwright, BrowserContext, Page
from human_typing import human_type_on, human_click, jitter
from human_browse import browse_before, browse_after


class XhsPublisher:
    PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?source=official"
    CDP_URL = "http://localhost:9222"

    def __init__(self, auto_submit: bool = True):
        self.auto_submit = auto_submit
        self._playwright = None
        self._browser = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    def start(self):
        """连接真实 Edge 浏览器"""
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.connect_over_cdp(self.CDP_URL)
        self.context = self._browser.contexts[0]
        self.context.add_init_script("""
            const orig = Element.prototype.attachShadow;
            Element.prototype.attachShadow = function(init) {
                return orig.call(this, { ...init, mode: 'open' });
            };
        """)
        print("✅ 已连接 Edge + Shadow DOM 劫持")

    def stop(self):
        """关闭页面并释放 Playwright 资源"""
        if self.page:
            try:
                self.page.close()
            except Exception:
                pass
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
        self.page = None
        self._browser = None
        self._playwright = None

    def publish(self, title: str, description: str, cover_image: str,
                tags: list[str] | None = None) -> bool:
        if self.context is None:
            raise RuntimeError("未启动浏览器，先调 start() 或设置 context")
        tags = tags or []
        _keep_open = False
        try:
            self.page = self.context.new_page()
            print("🌐 打开小红书...")
            self.page.goto(self.PUBLISH_URL, timeout=60000, wait_until="domcontentloaded")
            self.page.wait_for_timeout(3000)

            if "login" in self.page.url:
                print("⚠️ 未登录")
                return False
            print("✅ 已登录")

            # ── 浏览行为：假装看页面，不急着操作 ──
            browse_before(self.page)

            self._switch_tab()
            self._upload(cover_image)
            self._wait_editor()
            self._set_title(title)
            self._set_body(description, tags)

            # ── 浏览行为：假装校对新填的内容 ──
            browse_after(self.page)

            if self.auto_submit:
                self._publish()
                print("🎉 发布成功！")
            else:
                _keep_open = True
                print("⏸️  内容已填充完毕，请手动点击发布")
            return True
        except Exception as e:
            print(f"❌ {e}")
            import traceback; traceback.print_exc()
            return False
        finally:
            if self.page and not _keep_open:
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
        # 小红书 SPA：上传图片后 React 重渲染，固定等待比 networkidle 更可靠
        self.page.wait_for_timeout(8000)
        print("  ✅")

    def _wait_editor(self):
        print("⏳ 等编辑器...")
        self.page.wait_for_selector("input[placeholder*='填写标题']", timeout=15000)
        self.page.wait_for_timeout(2000)
        # 强制聚焦标题栏，确保键盘焦点在正确位置
        self.page.locator("input[placeholder*='填写标题']").first.focus()
        self.page.wait_for_timeout(1500)
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
        el = self.page.locator("input[placeholder*='填写标题']").first
        human_click(self.page, el)
        # SPA 可能在点击后触发重渲染导致焦点丢失，强制聚焦
        el.focus()
        self.page.wait_for_timeout(jitter(600))
        human_type_on(self.page, el, title, "xhs")
        self.page.wait_for_timeout(jitter(500))

    def _set_body(self, text, tags):
        print(f"📄 正文 ({len(text)}字)...")
        desc = self.page.locator("[contenteditable='true'], textarea").first
        human_click(self.page, desc)
        # 强制聚焦，防止 SPA 重渲染导致键盘焦点跑偏
        desc.focus()
        self.page.wait_for_timeout(jitter(600))
        human_type_on(self.page, desc, text, "xhs")
        self.page.wait_for_timeout(jitter(500))
        if tags:
            print(f"🏷️ 标签: {tags}")
            for t in tags:
                desc.type(f" #{t}", delay=jitter(15))
                self.page.wait_for_timeout(jitter(800))
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(jitter(300))

    def _publish(self):
        print("🚀 发布...")
        # Shadow DOM 已被劫持为 open，直接选择器
        btn = self.page.locator("button.ce-btn.bg-red")
        if btn.count() > 0:
            human_click(self.page, btn.first)
            print("  ✅ button.ce-btn.bg-red 点击")
        else:
            btn = self.page.get_by_role("button", name="发布")
            if btn.count() > 0:
                human_click(self.page, btn.first)
                print("  ✅ get_by_role 点击")
            else:
                self.page.keyboard.press("Control+Enter")
                print("  ✅ Ctrl+Enter")
        self.page.locator("text=发布成功").wait_for(timeout=60000)
        print("✅ 发布成功！")
