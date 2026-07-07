"""
B站专栏发布器 — 通过 CDP 连接真实 Edge 浏览器
编辑器在 iframe 内（ProseMirror），封面自动生成无需上传
"""
from patchright.sync_api import sync_playwright, BrowserContext, Page, Frame
import random
from human_typing import human_type, human_click, jitter
from human_browse import browse_before, browse_after
from human_behavior import distract_think, distract_mouse_leave, distract_edit_text, distract_post_fill
from stealth import generate_profile, build_stealth_script, build_extra_headers


class BilibiliPublisher:
    EDITOR_URL = "https://member.bilibili.com/platform/upload/text/new-edit"
    CDP_URL = "http://localhost:9222"

    def __init__(self, auto_submit: bool = True):
        self.auto_submit = auto_submit
        self._playwright = None
        self._browser = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self._profile = None

    def start(self):
        """连接真实 Edge 浏览器，注入 stealth 脚本"""
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.connect_over_cdp(self.CDP_URL)
        self.context = self._browser.contexts[0]

        # ── Stealth: 指纹伪装 ──
        self._profile = generate_profile()
        self.context.add_init_script(build_stealth_script(self._profile))
        extra_headers = build_extra_headers(self._profile)
        self.context.set_extra_http_headers(extra_headers)

        # ── Shadow DOM 劫持 ──
        self.context.add_init_script("""
            const orig = Element.prototype.attachShadow;
            Element.prototype.attachShadow = function(init) {
                return orig.call(this, { ...init, mode: 'open' });
            };
        """)
        print(f"✅ 已连接 Edge + Stealth (GPU: {self._profile.webgl_renderer[:40]}...)")

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

    @property
    def _editor_frame(self) -> Frame:
        """获取编辑器 iframe (name=116, url 包含 read-editor)"""
        for f in self.page.frames:
            if "read-editor" in f.url:
                return f
        raise RuntimeError("找不到编辑器 iframe")

    def publish(self, title: str, content: str,
                cover_image: str | None = None,
                tags: list[str] | None = None) -> bool:
        if self.context is None:
            raise RuntimeError("未启动浏览器，先调 start() 或设置 context")

        _keep_open = False
        try:
            self.page = self.context.new_page()
            print("🌐 打开 B 站专栏编辑器...")
            self.page.goto(self.EDITOR_URL, timeout=60000, wait_until="domcontentloaded")
            self.page.wait_for_timeout(5000)

            if "login" in self.page.url.lower():
                print("⚠️ 未登录"); return False
            print("✅ 已登录")

            # ── 浏览行为：假装看页面 ──
            browse_before(self.page)

            self._set_title(title)
            distract_think(self.page, duration_ms=random.randint(1000, 3000))
            self._set_content(content)
            if tags:
                self._set_tags(tags)
            distract_edit_text(self.page)
            distract_mouse_leave(self.page)

            # ── 浏览行为：假装校对 ──
            browse_after(self.page)
            distract_post_fill(self.page)

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

    def _set_title(self, title: str):
        title = title[:30]
        print(f"📝 标题: {title}")
        frame = self._editor_frame
        el = frame.locator("textarea[placeholder*='标题']").first
        human_click(self.page, el)
        self.page.wait_for_timeout(jitter(300))
        human_type(self.page, title, "standard")
        self.page.wait_for_timeout(jitter(500))
        print("  ✅")

    def _set_content(self, content: str):
        print(f"📄 正文 ({len(content)} 字)...")
        frame = self._editor_frame
        editor = frame.locator(".tiptap.ProseMirror").first
        human_click(self.page, editor)
        self.page.wait_for_timeout(jitter(500))

        human_type(self.page, content, "standard")

        print(f"  ✅ 输入完成")

    def _set_tags(self, tags: list[str]):
        print(f"🏷️ 话题: {tags}")
        frame = self._editor_frame

        for tag in tags:
            # 点击"添加话题"
            btn = frame.locator("button:has-text('添加话题')")
            if btn.count() == 0:
                # 可能已经在发布设置面板中
                btn = frame.locator("text=添加话题").first
            if btn.count() == 0:
                print("  ⚠️ 找不到添加话题按钮，跳过")
                break
            btn.first.click()
            self.page.wait_for_timeout(1000)

            # 话题输入框
            tag_input = frame.locator("input[placeholder*='话题']")
            if tag_input.count() == 0:
                # 可能是 contenteditable
                tag_input = frame.locator("[contenteditable='true']").last
            if tag_input.count() > 0:
                tag_input.first.click(); self.page.wait_for_timeout(jitter(300)); self.page.keyboard.type(tag, delay=jitter(60))
                self.page.wait_for_timeout(500)
                self.page.keyboard.press("Enter")
                self.page.wait_for_timeout(500)
            else:
                print(f"  ⚠️ 话题输入框未找到")
        print("  ✅")

    def _submit(self):
        print("🚀 发布...")
        frame = self._editor_frame

        # 发布按钮: button.vui_button--blue
        btn = frame.locator("button.vui_button--blue").first
        if btn.count() == 0:
            # 兜底：排除"设置""草稿"的发布按钮
            btn = frame.locator(
                "button:has-text('发布'):not(:has-text('设置')):not(:has-text('草稿'))"
            ).first
        if btn.count() == 0:
            raise Exception("找不到发布按钮")
        print(f"  📌 点击: {btn.inner_text()}")
        human_click(self.page, btn)
        self.page.wait_for_timeout(3000)

        # 检测发布结果
        self._wait_for_publish_result()

    def _wait_for_publish_result(self, timeout: int = 15000):
        print("⏳ 等待发布结果...")
        start = self.page.evaluate("Date.now()")
        success_kw = ["发布成功", "提交成功", "审核中", "待审核", "已发布"]

        while self.page.evaluate("Date.now()") - start < timeout:
            try:
                # toast 提示
                toast = self.page.locator("[class*='toast'], [class*='message'], [class*='notice']")
                if toast.count() > 0:
                    toast_text = toast.first.inner_text()
                    for kw in success_kw:
                        if kw in toast_text:
                            print(f"  ✅ {toast_text.strip()}")
                            return

                # URL 跳转 = 成功
                url = self.page.url
                if "upload" not in url and "edit" not in url:
                    print("  ✅ 已跳转，发布成功")
                    return
            except Exception:
                pass

            self.page.wait_for_timeout(1000)

        print("  ⚠️ 未检测到明确提示，请手动确认")
