"""
微博头条文章发布器 — 通过 CDP 连接真实 Edge 浏览器
ProseMirror 编辑器，支持 Markdown
"""
import random
from patchright.sync_api import sync_playwright, BrowserContext, Page
from human_typing import human_type, human_click, jitter
from human_browse import browse_before, browse_after
from human_behavior import distract_think, distract_mouse_leave, distract_edit_text, distract_post_fill
from stealth import generate_profile, build_stealth_script, build_extra_headers


class WeiboPublisher:
    EDITOR_URL = "https://card.weibo.com/article/v5/editor#/draft"
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

    def publish(self, title: str, content: str,
                cover_image: str | None = None,
                tags: list[str] | None = None) -> bool:
        if self.context is None:
            raise RuntimeError("未启动浏览器，先调 start() 或设置 context")

        _keep_open = False
        try:
            self.page = self.context.new_page()
            print("🌐 打开微博头条文章编辑器...")
            self.page.goto(self.EDITOR_URL, timeout=60000, wait_until="domcontentloaded")
            self.page.wait_for_timeout(5000)

            if "login" in self.page.url.lower():
                print("⚠️ 未登录"); return False
            print("✅ 已登录")

            # ── 浏览行为：假装看页面 ──
            browse_before(self.page)

            self._wait_editor()
            self._set_title(title)
            distract_think(self.page, duration_ms=random.randint(1000, 3000))
            self._set_content(content)

            if cover_image:
                self._set_cover(cover_image)
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

    def _wait_editor(self):
        print("⏳ 等待编辑器渲染...")
        self.page.wait_for_selector("textarea[placeholder='请输入标题']", timeout=15000)
        self.page.wait_for_timeout(2000)
        print("  ✅ 编辑器已就绪")

    def _set_title(self, title: str):
        title = title[:32]
        print(f"📝 标题: {title}")
        el = self.page.locator("textarea[placeholder='请输入标题']").first
        human_click(self.page, el)
        human_type(self.page, title, "standard")
        self.page.wait_for_timeout(jitter(500))
        print("  ✅")

    def _set_content(self, content: str):
        print(f"📄 正文 ({len(content)} 字)...")
        self.page.evaluate("""
            const el = document.querySelector('.tiptap.ProseMirror');
            if (el) el.focus();
        """)
        self.page.wait_for_timeout(jitter(500))

        human_type(self.page, content, "standard")

        print(f"  ✅ 输入完成")

    def _set_cover(self, image_path: str):
        """设置封面 — 处理 .cover-empty(新文章) 或 .cover-preview(已有封面)"""
        print(f"🖼️ 设置封面: {image_path}")

        # 根据状态选择入口
        cover_empty = self.page.locator(".cover-empty")
        cover_preview = self.page.locator(".cover-preview")

        if cover_preview.count() > 0:
            # 已有封面，点"替换封面图"
            replace_btn = cover_preview.locator("text=替换封面图").first
            if replace_btn.count() > 0:
                replace_btn.click(force=True)
                self.page.wait_for_timeout(2000)
        elif cover_empty.count() > 0:
            cover_empty.first.click(force=True)
            self.page.wait_for_timeout(2000)
        else:
            print("  ⚠️ 找不到封面入口")
            return

        # 在弹窗中切到"图片库"，点"上传"
        gallery_tab = self.page.locator(".n-modal").locator("text=图片库").first
        if gallery_tab.count() > 0:
            gallery_tab.click(force=True)
            self.page.wait_for_timeout(1000)

        # 点击"上传"，用 file_chooser 监听文件选择
        upload_btn = self.page.locator(".n-modal button:has-text('上传')").first
        if upload_btn.count() == 0:
            upload_btn = self.page.locator("button:has-text('上传')").first
        if upload_btn.count() == 0:
            print("  ⚠️ 找不到上传按钮"); return

        with self.page.expect_file_chooser() as fc:
            upload_btn.click(force=True)
        fc.value.set_files(image_path)
        # 等图片加载完成再选中
        self.page.wait_for_timeout(4000)

        # 图片上有 select-mask 遮罩，用 force=True 或点父容器
        imgs = self.page.locator(".n-modal img:not([class*='avatar'])")
        print(f"  图片数: {imgs.count()}")

        if imgs.count() > 0:
            # 点图片的父容器（绕过 select-mask）
            parent = imgs.first.locator("..")
            parent.click(force=True)
            self.page.wait_for_timeout(1000)
            print("  ✅ 已选中图片")
        else:
            print("  ⚠️ 未找到图片")

        # 下一步
        next_btn = self.page.locator(".n-modal button:has-text('下一步')").first
        if next_btn.count() > 0:
            next_btn.click(force=True)
            self.page.wait_for_timeout(3000)

        # 裁剪确认
        ok_btn = self.page.locator("button:has-text('确定'):not(:has-text('取消'))").first
        if ok_btn.count() > 0:
            ok_btn.click(force=True)
        else:
            self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(2000)

        # 裁剪后再点下一步
        next2 = self.page.locator(".n-modal button:has-text('下一步')").first
        if next2.count() > 0:
            next2.click(force=True)
            self.page.wait_for_timeout(2000)

        print("  ✅ 封面已设置")

    def _submit(self):
        print("🚀 发布...")

        self.page.evaluate("""
            document.querySelectorAll('.n-modal-mask').forEach(m => m.style.display = 'none');
        """)
        self.page.wait_for_timeout(500)

        next_btn = self.page.locator("button:has-text('下一步')").first
        if next_btn.count() == 0:
            raise Exception("找不到下一步按钮")
        print(f"  📌 点击: {next_btn.inner_text()}")
        human_click(self.page, next_btn, force=True)
        self.page.wait_for_timeout(3000)

        self.page.evaluate("""
            document.querySelectorAll('.n-modal-mask').forEach(m => m.style.display = '');
        """)
        self.page.wait_for_timeout(2000)

        # 等弹窗渲染完成，按钮出现
        self.page.wait_for_selector("button:has-text('发布')", timeout=10000)
        publish_btn = self.page.locator("button:has-text('发布')").first
        if publish_btn.count() == 0:
            raise Exception("找不到发布按钮")
        print(f"  📌 点击: {publish_btn.inner_text()}")
        human_click(self.page, publish_btn, force=True)
        self.page.wait_for_timeout(3000)

        self._wait_for_publish_result()

    def _wait_for_publish_result(self, timeout: int = 15000):
        print("⏳ 等待发布结果...")
        start = self.page.evaluate("Date.now()")
        success_kw = ["发布成功", "提交成功", "审核中", "已发布", "创建成功"]

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
                if "editor" not in url and "draft" not in url:
                    print("  ✅ 已跳转，发布成功")
                    return
            except Exception:
                pass

            self.page.wait_for_timeout(1000)

        print("  ⚠️ 未检测到明确提示，请手动确认")
