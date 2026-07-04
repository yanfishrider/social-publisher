"""
百家号图文发布器 — 通过 CDP 连接真实 Edge 浏览器
百度百家号反爬等级高，必须用真实浏览器避免检测
"""
from playwright.sync_api import sync_playwright, BrowserContext, Page
from human_typing import human_type, human_click, jitter


class BaijiahaoPublisher:
    EDITOR_URL = "https://baijiahao.baidu.com/builder/rc/edit?type=news&is_from_cms=1"
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
            print("🌐 打开百家号编辑器...")
            self.page.goto(self.EDITOR_URL, timeout=60000, wait_until="domcontentloaded")
            self.page.wait_for_timeout(5000)
            
            if not self._check_login():
                print("⚠️ 未登录"); return False
            print("✅ 已登录")
            
            self._wait_editor()
            self._set_title(title)
            self._set_content(content)
            self._upload_cover(cover_image)
            
            if tags:
                self._set_tags(tags)
            
            if self.auto_submit:
                self._submit()
                print("🎉 发布成功！")
            else:
                _keep_open = True
                print("⏸️  内容已填充完毕，请手动点击发布")
            return True
            
        except Exception as e:
            print(f"❌ 发布失败: {e}")
            import traceback; traceback.print_exc()
            return False
        finally:
            if self.page and not _keep_open:
                try:
                    self.page.wait_for_timeout(3000)
                    self.page.close()
                except Exception:
                    pass
    
    def _check_login(self) -> bool:
        url = self.page.url
        if "passport.baidu.com" in url or "/login" in url:
            return False
        if self.page.locator("[data-testid='news-title-input']").count() > 0:
            return True
        return len(self.page.locator("body").inner_text()) > 100
    
    def _wait_editor(self):
        print("⏳ 等待编辑器渲染...")
        self.page.wait_for_selector("[data-testid='news-title-input']", timeout=15000)
        self.page.wait_for_timeout(2000)
        print("  ✅ 编辑器已就绪")
    
    # ── 1. 标题（第 0 个 Lexical editor，最多 64 字）──
    
    def _set_title(self, title: str):
        title = title[:64]
        print(f"📝 标题: {title}")
        
        editor = self.page.locator("[data-lexical-editor='true']").first
        human_click(self.page, editor)
        self.page.wait_for_timeout(jitter(300))
        self.page.keyboard.press("Control+a")
        self.page.wait_for_timeout(jitter(100))
        self.page.keyboard.press("Backspace")
        self.page.wait_for_timeout(jitter(200))
        human_type(self.page, title, "baidu")
        self.page.wait_for_timeout(jitter(500))
        print("  ✅")
    
    # ── 2. 正文（UEditor iframe #ueditor_0）──

    def _set_content(self, content: str):
        print(f"📄 正文 ({len(content)} 字)...")

        # 正文在 UEditor iframe 内
        frame = self.page.frame_locator("#ueditor_0")
        body = frame.locator("body")

        human_click(self.page, body)
        self.page.wait_for_timeout(jitter(500))

        human_type(self.page, content, "baidu")

        print(f"  ✅ 输入完成")
    
    # ── 3. 封面（必填，弹窗模式）──
    
    def _upload_cover(self, image_path: str):
        print(f"🖼️ 上传封面: {image_path}")
        
        # 1. 点击 "选择封面" 打开弹窗
        cover_btn = self.page.locator("text=选择封面").first
        if cover_btn.count() == 0:
            raise Exception("找不到封面入口")
        cover_btn.click()
        self.page.wait_for_timeout(2000)
        print("  📌 封面弹窗已打开")
        
        # 2. 上传文件 — 弹窗内的 file input（.cheetah-upload 内）
        file_input = self.page.locator(".cheetah-upload input[type='file']")
        if file_input.count() == 0:
            raise Exception("找不到封面弹窗内的文件上传 input")
        file_input.first.set_input_files(image_path)
        self.page.wait_for_timeout(5000)  # 等图片加载完成
        print("  ✅ 文件已选择")
        
        # 3. 确认 — 用 cheetah-btn-primary（React 组件）
        confirm_btn = self.page.locator(".cheetah-btn-primary:has-text('确定')")
        confirm_btn.first.wait_for(state="visible", timeout=15000)
        confirm_btn.first.click()
        self.page.wait_for_timeout(2000)
        print("  ✅ 封面已确认")
    
    # ── 4. 标签（选填）──
    
    def _set_tags(self, tags: list[str]):
        print(f"🏷️ 标签: {tags}")
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        self.page.wait_for_timeout(1000)
        
        tag_input = self.page.locator("[placeholder*='标签']")
        if tag_input.count() > 0:
            tag_input.first.click()
            tag_input.first.fill(",".join(tags))
            self.page.wait_for_timeout(500)
            self.page.keyboard.press("Enter")
            print("  ✅")
        else:
            print("  ⚠️ 找不到标签输入，跳过")
    
    # ── 5. 发布 ──
    
    def _submit(self):
        print("🚀 提交发布...")
        self.page.wait_for_timeout(1000)
        
        btn = self.page.locator("[data-testid='publish-btn']")
        if btn.count() > 0:
            human_click(self.page, btn.first)
            print("  ✅ 点击发布按钮")
        else:
            raise Exception("找不到发布按钮")
        
        self._wait_for_publish_result()
    
    def _wait_for_publish_result(self, timeout: int = 30000):
        print("⏳ 等待发布结果...")
        start = self.page.evaluate("Date.now()")
        success_kw = ["发布成功", "提交成功", "审核中", "待审核"]
        failure_kw = ["失败", "不符合", "重复", "错误", "异常"]
        
        while self.page.evaluate("Date.now()") - start < timeout:
            body_text = self.page.locator("body").inner_text()
            
            for kw in success_kw:
                if kw in body_text:
                    print(f"  ✅ 检测到: {kw}")
                    self.page.wait_for_timeout(2000)
                    return
            
            for kw in failure_kw:
                if kw in body_text:
                    lines = [l for l in body_text.split("\n") if kw in l]
                    raise Exception(f"发布被拒: {lines[0] if lines else kw}")
            
            self.page.wait_for_timeout(1000)
        
        print("  ⚠️ 超时，请手动检查")
