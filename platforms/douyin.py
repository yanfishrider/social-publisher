"""
抖音图文发布器 — 通过 CDP 连接真实 Edge 浏览器
必须先上传图片才能进入编辑页，标题≤20字，正文~1000字
"""
from patchright.sync_api import sync_playwright, BrowserContext, Page
from human_typing import human_type, human_click, jitter
from human_browse import browse_before, browse_after


class DouyinPublisher:
    UPLOAD_URL = "https://creator.douyin.com/creator-micro/content/upload"
    CDP_URL = "http://localhost:9222"

    def __init__(self, auto_submit: bool = True):
        self.auto_submit = auto_submit
        self._playwright = None
        self._browser = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    def start(self):
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

    def publish(self, title: str, content: str, cover_image: str,
                tags: list[str] | None = None) -> bool:
        if self.context is None:
            raise RuntimeError("未启动浏览器，先调 start() 或设置 context")

        _keep_open = False
        try:
            self.page = self.context.new_page()
            print("🌐 打开抖音创作页...")
            self.page.goto(self.UPLOAD_URL, timeout=60000, wait_until="domcontentloaded")
            self.page.wait_for_timeout(5000)

            if "login" in self.page.url.lower():
                print("⚠️ 未登录"); return False
            print("✅ 已登录")

            # ── 浏览行为：假装看页面 ──
            browse_before(self.page)

            # 1. 上传图片 → 进入编辑页
            self._upload_image(cover_image)

            # 2. 填写内容
            self._set_title(title)
            self._set_content(content)
            if tags:
                self._set_tags(tags)
            
            # ── 浏览行为：假装校对 ──
            browse_after(self.page)

            if self.auto_submit:
                self._submit()
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
                try:
                    self.page.wait_for_timeout(2000)
                    self.page.close()
                except Exception:
                    pass

    def _upload_image(self, image_path: str):
        """上传图片并等待跳转到编辑页"""
        print(f"🖼️ 上传: {image_path}")

        # 点击"发布图文"tab
        tab = self.page.locator(".tab-item-BcCLTS").nth(1)
        tab.click()
        self.page.wait_for_timeout(1000)

        # 图片 input 是第二个 file input
        self.page.locator("input[type='file']").nth(1).set_input_files(image_path)
        self.page.wait_for_timeout(5000)

        # 处理"上次未发布"草稿提示
        discard = self.page.locator("text=放弃")
        if discard.count() > 0:
            discard.first.click()
            self.page.wait_for_timeout(2000)

        # 等待跳转到编辑页
        self.page.wait_for_url("**/post/image**", timeout=30000)
        self.page.wait_for_timeout(3000)
        print("  ✅ 已进入编辑页")

    def _set_title(self, title: str):
        title = title[:20]
        print(f"📝 标题: {title}")
        el = self.page.locator("input[placeholder='添加作品标题']").first
        human_click(self.page, el)
        self.page.wait_for_timeout(jitter(300))
        human_type(self.page, title, "byte_dance")
        self.page.wait_for_timeout(jitter(500))
        print("  ✅")

    def _set_content(self, content: str):
        print(f"📄 正文 ({len(content)} 字)...")
        editor = self.page.locator(".zone-container.editor-kit-container").first
        human_click(self.page, editor)
        self.page.wait_for_timeout(jitter(500))

        # 抖音限制 ~1000 字
        human_type(self.page, content[:1000], "byte_dance")

        print(f"  ✅ 输入完成")

    def _set_tags(self, tags: list[str]):
        print(f"🏷️ 话题: {tags}")
        for tag in tags:
            btn = self.page.locator("text=#添加话题").first
            if btn.count() == 0:
                print("  ⚠️ 找不到话题入口，跳过")
                break
            btn.click()
            self.page.wait_for_timeout(1000)

            # 话题输入框
            tag_input = self.page.locator("input[placeholder*='话题']")
            if tag_input.count() == 0:
                tag_input = self.page.locator("[contenteditable='true']").last
            if tag_input.count() > 0:
                tag_input.first.click(); self.page.wait_for_timeout(jitter(300)); self.page.keyboard.type(tag, delay=jitter(60))
                self.page.wait_for_timeout(500)
                self.page.keyboard.press("Enter")
                self.page.wait_for_timeout(500)
        print("  ✅")

    def _submit(self):
        print("🚀 发布...")
        btn = self.page.locator("button.button-dhlUZE.primary-cECiOJ").first
        if btn.count() == 0:
            btn = self.page.locator("button:has-text('发布')").first
        if btn.count() == 0:
            raise Exception("找不到发布按钮")
        print(f"  📌 点击: {btn.inner_text()}")
        human_click(self.page, btn)
        self.page.wait_for_timeout(3000)

        self._wait_for_publish_result()

    def _wait_for_publish_result(self, timeout: int = 15000):
        print("⏳ 等待发布结果...")
        start = self.page.evaluate("Date.now()")
        success_kw = ["发布成功", "提交成功", "审核中", "已发布"]

        while self.page.evaluate("Date.now()") - start < timeout:
            try:
                toast = self.page.locator("[class*='toast'], [class*='message'], [class*='notice']")
                if toast.count() > 0:
                    toast_text = toast.first.inner_text()
                    for kw in success_kw:
                        if kw in toast_text:
                            print(f"  ✅ {toast_text.strip()}")
                            return

                url = self.page.url
                if "upload" not in url and "post/image" not in url:
                    print("  ✅ 已跳转，发布成功")
                    return
            except Exception:
                pass

            self.page.wait_for_timeout(1000)

        print("  ⚠️ 未检测到明确提示，请手动确认")
