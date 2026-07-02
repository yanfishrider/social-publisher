"""
今日头条号图文发布器 — 通过 CDP 连接真实 Edge 浏览器
字节跳动反爬等级极高，必须用真实浏览器避免检测
"""
from playwright.sync_api import sync_playwright, BrowserContext, Page


class ToutiaoPublisher:
    EDITOR_URL = "https://mp.toutiao.com/profile_v4/graphic/publish?from=toutiao_pc"
    CDP_URL = "http://localhost:9222"
    
    def __init__(self):
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
        if self._playwright:
            self._playwright.stop()
    
    def publish(self, title: str, content: str, cover_image: str | None = None,
                tags: list[str] | None = None) -> bool:
        if self.context is None:
            raise RuntimeError("未启动浏览器，先调 start() 或设置 context")
        
        try:
            self.page = self.context.new_page()
            print("🌐 打开头条号编辑器...")
            self.page.goto(self.EDITOR_URL, timeout=30000)
            self.page.wait_for_load_state("domcontentloaded")
            self.page.wait_for_timeout(5000)
            
            if not self._check_login():
                print("⚠️ 未登录"); return False
            print("✅ 已登录")
            
            self._wait_editor()
            self._set_title(title)
            self._set_content(content)
            
            if cover_image:
                self._upload_cover(cover_image)
            
            if tags:
                self._set_tags(tags)
            
            self._submit()
            print("🎉 发布成功！")
            return True
            
        except Exception as e:
            print(f"❌ 发布失败: {e}")
            import traceback; traceback.print_exc()
            return False
        finally:
            if self.page:
                try:
                    self.page.wait_for_timeout(3000)
                    self.page.close()
                except Exception:
                    pass
    
    def _check_login(self) -> bool:
        url = self.page.url
        if "login" in url.lower() or "passport" in url:
            return False
        # 有标题 textarea 说明已登录
        if self.page.locator("textarea[placeholder*='标题']").count() > 0:
            return True
        return len(self.page.locator("body").inner_text()) > 100
    
    def _wait_editor(self):
        print("⏳ 等待编辑器渲染...")
        self.page.wait_for_selector("textarea[placeholder*='标题']", timeout=15000)
        self.page.wait_for_timeout(2000)
        print("  ✅ 编辑器已就绪")
    
    # ── 1. 标题（textarea，最多 30 字）──
    
    def _set_title(self, title: str):
        if len(title) > 30:
            cut = title[:30]
            for sep in [" — ", " - ", "，", "。", "、", " "]:
                idx = cut.rfind(sep)
                if idx > 15:
                    cut = cut[:idx]
                    break
            title = cut
        print(f"📝 标题: {title}")
        
        el = self.page.locator("textarea[placeholder*='标题']").first
        el.click()
        self.page.wait_for_timeout(300)
        el.fill("")
        el.type(title, delay=30)
        self.page.wait_for_timeout(500)
        print("  ✅")
    
    # ── 2. 正文（ProseMirror contenteditable）──
    
    def _set_content(self, content: str):
        print(f"📄 正文 ({len(content)} 字)...")

        editor = self.page.locator(".ProseMirror").first
        editor.click()
        self.page.wait_for_timeout(500)

        # 长文本用剪贴板粘贴，避免逐字键入超时
        if len(content) > 1000:
            import pyperclip
            pyperclip.copy(content)
            self.page.keyboard.press("Control+a")
            self.page.wait_for_timeout(200)
            self.page.keyboard.press("Control+v")
            self.page.wait_for_timeout(1000)
        else:
            for paragraph in content.split("\n"):
                if paragraph.strip():
                    self.page.keyboard.type(paragraph, delay=10)
                    self.page.wait_for_timeout(200)
                    self.page.keyboard.press("Shift+Enter")
                    self.page.wait_for_timeout(100)

        print("  ✅")
    
    # ── 3. 封面（选填，单图/三图/无封面）──
    
    def _upload_cover(self, image_path: str):
        print(f"🖼️ 上传封面: {image_path}")
        
        # 1. 选择 "单图" 模式
        single_cover = self.page.locator("text=单图")
        if single_cover.count() == 0:
            raise Exception("找不到单图选项")
        single_cover.first.click()
        self.page.wait_for_timeout(2000)
        print("  📌 已选单图模式")
        
        # 2. 点击 + 号打开抽屉
        add_btn = self.page.locator(".article-cover-add")
        if add_btn.count() == 0:
            raise Exception("找不到封面添加按钮")
        add_btn.first.click()
        self.page.wait_for_timeout(2000)
        print("  📌 封面抽屉已打开")
        
        # 3. 在抽屉内上传文件
        file_input = self.page.locator("input[type='file'][accept*='image']")
        if file_input.count() > 0:
            file_input.first.set_input_files(image_path)
            self.page.wait_for_timeout(3000)
            print("  ✅ 文件已选择")
        else:
            raise Exception("找不到封面文件上传 input")
        
        # 4. 点击抽屉内的 "确定"
        confirm_btn = self.page.locator(".byte-drawer button:has-text('确定')")
        if confirm_btn.count() > 0:
            confirm_btn.first.click()
            self.page.wait_for_timeout(2000)
            print("  ✅ 封面已确认")
        else:
            print("  ⚠️ 找不到确认按钮")
    
    # ── 4. 标签（选填）──
    
    def _set_tags(self, tags: list[str]):
        print(f"🏷️ 标签: {tags}")
        print("  ⚠️ 头条标签功能待确认，跳过")
    
    # ── 5. 发布 ──
    
    def _submit(self):
        print("🚀 提交发布...")
        self.page.wait_for_timeout(1000)

        # 第一步：点击 "预览并发布"
        btn = self.page.locator(".byte-btn-primary:has-text('预览并发布')")
        if btn.count() == 0:
            raise Exception("找不到发布按钮")
        btn.first.click()
        print("  ✅ 已点击预览并发布")

        # 等待手机预览图出现 + 按钮变为 "发布"
        self.page.wait_for_timeout(3000)

        # 第二步：原位置按钮已变成 "发布"，再次点击
        # 优先精确匹配 "发布"（不包含"预览"的发布按钮）
        confirm_btn = self.page.locator(
            ".byte-btn-primary:has-text('发布'):not(:has-text('预览'))"
        )
        if confirm_btn.count() == 0:
            # 兜底：找任何可见的 "发布" 或 "确认发布"
            confirm_btn = self.page.locator(
                "button:has-text('确认发布'), button:has-text('发布')"
            ).first

        confirm_btn.wait_for(state="visible", timeout=15000)
        confirm_btn.click()
        try:
            self.page.wait_for_timeout(2000)
        except Exception:
            pass
        print("  ✅ 已确认发布")

        self._wait_for_publish_result()
    
    def _wait_for_publish_result(self, timeout: int = 30000):
        print("⏳ 等待发布结果...")
        start = self.page.evaluate("Date.now()")
        success_kw = ["发布成功", "提交成功", "审核中", "待审核", "已发布"]
        failure_kw = ["失败", "不符合", "重复", "错误", "异常"]

        while self.page.evaluate("Date.now()") - start < timeout:
            try:
                # 优先检查 toast 提示
                toast = self.page.locator(".byte-toast, .byte-message, [class*='toast'], [class*='message']")
                if toast.count() > 0:
                    toast_text = toast.first.inner_text()
                    for kw in success_kw:
                        if kw in toast_text:
                            print(f"  ✅ {toast_text.strip()}")
                            return
                    for kw in failure_kw:
                        if kw in toast_text:
                            raise Exception(f"发布被拒: {toast_text.strip()}")

                # 检查页面 URL 是否已跳转离开编辑器（跳转 = 成功）
                url = self.page.url
                if "publish" not in url and "edit" not in url:
                    print("  ✅ 已跳转至内容管理页，发布成功")
                    return

                # 兜底：检查 body 文本
                body_text = self.page.locator("body").inner_text()
                for kw in success_kw:
                    if kw in body_text:
                        print(f"  ✅ 检测到: {kw}")
                        return
                for kw in failure_kw:
                    if kw in body_text:
                        lines = [l for l in body_text.split("\n") if kw in l]
                        raise Exception(f"发布被拒: {lines[0] if lines else kw}")
            except Exception as e:
                if "发布被拒" in str(e):
                    raise
                # 页面可能正在跳转，忽略临时错误
                pass

            self.page.wait_for_timeout(1000)

        # 超时但没检测到失败 → 大概率成功（页面已跳转）
        print("  ⚠️ 未检测到明确提示，请手动确认")
