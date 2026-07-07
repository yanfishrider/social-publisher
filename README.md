# social-publisher

多平台社交媒体自动发布工具，基于 Playwright + CDP 连接真实浏览器，绕过反爬检测。

支持从 PDF 宣传册一键生成多平台适配文案并自动发布。

## ⚠️ 封号风险警告

**此项目存在严重的封号风险，请务必阅读。**

- **真实案例**：开发者在测试「逐字输入模拟真人打字」功能时，今日头条账号被**永久封禁**，无申诉渠道。
- **风险来源**：所有平台（尤其是字节系：头条、抖音）对自动化操作有严格检测。即使通过 CDP 连接真实浏览器、模拟真人打字速度，仍可能触发风控。
- **逐字输入 ≠ 安全**：`keyboard.type(delay=60)` 逐字键入看似像真人，但平台的键盘事件分析远超打字速度——包括按键间隔分布、输入节奏模式、光标行为等，模拟打字可能比剪贴板粘贴更容易被检测（因为行为模式单一）。
- **建议**：
  1. **降低发布频率**：避免短时间内连续发布，间隔至少 30 分钟以上。
  2. **不要用主账号测试**：使用小号或专门创建的测试账号。
  3. **混入人工操作**：不要完全自动化，偶尔手动打断流程（暂停、修改、预览）。
  4. **内容要正常**：严禁标题或正文包含「测试」「自动化」「Playwright」等敏感词。
  5. **优先用 Web 界面手动发布**：`server.py` 提供的 Web 页面至少有人工确认环节。

**继续使用此工具即表示你已充分了解上述风险，并自行承担可能的封号后果。**

## 支持平台

| 平台 | 内容类型 | 反爬等级 | 状态 |
|------|----------|----------|------|
| 小红书 (Xiaohongshu) | 图文笔记 | Medium | ✅ |
| 百家号 (Baijiahao) | 长文 | High | ✅ |
| 今日头条 (Toutiao) | 长文 | Very High | ✅ |
| B站专栏 (Bilibili) | 专栏文章 | Medium | ✅ |
| 抖音 (Douyin) | 图文 | High | ✅ |
| 微博 (Weibo) | 头条文章 | Medium | ✅ |
| 搜狐号 (Sohu) | 长文 | Low | ⏳ 审核问题暂缓 |

## 前置条件

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) 包管理器
- Windows / macOS
- Edge 浏览器（用于 CDP 连接绕过反爬）

## 快速开始

```bash
# 1. 安装依赖
uv sync

# 2. 启动 Edge 调试模式（必须，用于 CDP 连接）
"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222

# 3. 手动登录各平台（只需一次）
uv run python main.py login xiaohongshu
uv run python main.py login baijiahao
uv run python main.py login toutiao
uv run python main.py login bilibili
uv run python main.py login douyin
uv run python main.py login weibo
# 登录完成后按 Enter 关闭

# 4. 发布内容（使用 --use-edge 通过 CDP 连接绕过反爬）
# 小红书（封面图必填，标题 ≤20 字）
uv run python main.py publish xiaohongshu \
  --title "完整标题" --short-title "短标题" \
  --cover-image ./cover.png --content-file ./article.md \
  --tags "标签1,标签2" --use-edge

# 百家号（封面图必填，标题 ≤64 字）
uv run python main.py publish baijiahao \
  --title "文章标题" --content-file ./article.md \
  --cover-image ./cover.png --use-edge

# 今日头条（封面图选填，标题 ≤30 字）
uv run python main.py publish toutiao \
  --title "文章标题" --content-file ./article.md \
  --cover-image ./cover.png --use-edge

# B 站专栏（封面图自动生成，标题 ≤64 字）
uv run python main.py publish bilibili \
  --title "专栏标题" --content-file ./article.md --use-edge

# 抖音图文（封面图必填）
uv run python main.py publish douyin \
  --title "图文标题" --content-file ./article.md \
  --cover-image ./cover.png --use-edge

# 微博头条文章（封面图选填）
uv run python main.py publish weibo \
  --title "文章标题" --content-file ./article.md \
  --cover-image ./cover.png --tags "标签1,标签2" --use-edge

# 一键全平台发布
uv run python main.py publish all \
  --title "文章标题" --short-title "短标题" \
  --content-file ./article.md --cover-image ./cover.png \
  --tags "标签1,标签2" --use-edge
```

## PDF → 多平台发布 完整流程

### 1. PDF 分析与转换

```
python pdf_to_markdown.py 宣传手册.pdf --diagnose    # 诊断 PDF 类型
python pdf_to_markdown.py 宣传手册.pdf                # 转换为 content/*.md
```

**⚠️ 重要：转曲 PDF 需要 Hermes AI 参与**

PDF 分为两种类型：

| 类型 | 说明 | 处理方式 |
|------|------|----------|
| 文字型 PDF | 文字可直接提取 | `pdf_to_markdown.py` 全自动完成 |
| 转曲 PDF | 文字被转为矢量曲线（常见于 CorelDRAW/Illustrator 导出的宣传册） | 脚本渲染页面为图片 → **需要 Hermes AI（vision）逐页读取文字** → 手动整合为 Markdown |

判断标准：`--diagnose` 输出中「平均每页文字」为 0 字即为转曲 PDF。

### 2. 内容改写与发布

发布时会**自动检测内容格式并适配**：

| 平台 | 内容处理 | 触发条件 |
|------|----------|----------|
| 小红书 | `content_rewriter.py` 精简为 ~80 字短文案 | >500 字 |
| 百家号 | `content_rewriter.py` 转为纯文本段落 | >500 字 |
| 头条号 | `content_rewriter.py` 转为纯文本段落 | >500 字 |
| B站专栏 | `content_rewriter.py` 转为纯文本段落 | >500 字 |
| 抖音图文 | `content_rewriter.py` 精简为短文案 | >800 字 |
| 微博头条 | `content_rewriter.py` 转为纯文本段落 | >500 字 |

使用 `--content-text` 直传短文本则跳过自动改写。

```bash
# 六平台一键发布（使用同一份 content/*.md）
uv run python main.py publish all --use-edge \
  --title "标题" --short-title "短标题" \
  --content-file content/xxx.md --cover-image content/xxx.png \
  --tags "标签1,标签2"
```

## 项目结构

```
social-publisher/
├── main.py                  # CLI 入口 (login + publish)
├── server.py                # FastAPI Web 界面 + SSE 实时日志
├── publish_worker.py        # 子进程发布 worker（隔离 Playwright）
├── config.py                # 配置加载 (PublishConfig dataclass)
├── browser_manager.py       # 浏览器生命周期管理
├── image_utils.py           # PIL 图片压缩
├── human_typing.py          # 真人打字模拟（逐字+打错+贝塞尔速度）
├── human_browse.py          # 浏览行为模拟（滚动/停留/鼠标移动）
├── rate_limiter.py          # 频率控制（防封号）
├── pdf_to_markdown.py       # PDF → Markdown 转换工具
├── docx_to_markdown.py      # DOCX → Markdown 转换工具
├── content_rewriter.py      # 内容改写（适配各平台格式）
├── content/                 # 内容素材（从 PDF 生成，不推送）
│   ├── xxx.md               #   从 PDF 提取的 Markdown
│   └── xxx.png              #   封面图
├── templates/
│   └── index.html           # Web 界面 HTML
├── uploads/                 # 上传的封面图缓存
├── platforms/
│   ├── xiaohongshu.py       # 小红书发布器
│   ├── baijiahao.py         # 百家号发布器
│   ├── toutiao.py           # 今日头条发布器
│   ├── bilibili.py          # B站专栏发布器
│   ├── douyin.py            # 抖音图文发布器
│   └── weibo.py             # 微博头条文章发布器
├── pyproject.toml           # 项目元数据 + 依赖
├── .env.example             # 环境变量模板
└── README.md
```

## Web 界面

启动 Web 管理界面，支持多平台同时填充、SSE 实时日志：

```bash
uv run uvicorn server:app --reload --port 8083
```

打开 http://127.0.0.1:8083/，功能包括：

- **多平台选择**：一次勾选 1~6 个平台，串行填充
- **手动模式**（默认勾选）：只填充图文不点击发布，填充后 Edge 页面保留供人工检查
- **自动模式**：填充完成后自动点击发布按钮
- **封面压缩**：>5MB 自动压缩
- **内容改写预览**：长文自动适配各平台格式
- **频率控制**：内置 `rate_limiter` 限制发布频率
- **发布统计**：`GET /stats` 查看各平台发布计数

### 手动模式工作流程

```
勾选平台 A,B,C → 点"填充" →
  Worker A: 连CDP → 开页面 → 模拟浏览 → 填标题/正文 → 断CDP(页面留着) → 退出
  Worker B: 连CDP → 开页面 → 模拟浏览 → 填标题/正文 → 断CDP(页面留着) → 退出
  Worker C: 连CDP → 开页面 → 模拟浏览 → 填标题/正文 → 断CDP(页面留着) → 退出
→ 全部填充完毕，Edge 中 3 个页面就绪，手动逐个发布
```

## 频率控制

`rate_limiter.py` 控制各平台发布间隔，防止触发风控：

| 平台 | 最小间隔 |
|------|----------|
| 小红书 | 30 分钟 |
| 抖音 | 30 分钟 |
| 百家号 | 20 分钟 |
| 头条号 | 30 分钟 |
| B 站 | 15 分钟 |
| 微博 | 15 分钟 |

Web 界面和 CLI 均受理频率限制，超频自动跳过。

## 浏览行为模拟

`human_browse.py` 在填充前后模拟真人浏览：

- **填充前** (`browse_before`)：随机滚动页面、鼠标移动、停顿，模拟"看页面再操作"
- **填充后** (`browse_after`)：回滚到顶部、停留检查、随机点击空白区域，模拟"校对新填内容"

所有平台发布器均已集成。

## 平台特性

| 平台 | 编辑器 | 特殊处理 |
|------|--------|----------|
| 小红书 | 标准 textarea | Shadow DOM 劫持 |
| 百家号 | UEditor iframe | 逐字输入 delay=60ms |
| 今日头条 | ProseMirror 编辑器 | 逐字输入 delay=60ms |
| B站专栏 | ProseMirror (iframe) | 逐字输入 delay=60ms |
| 抖音 | contenteditable div | 逐字输入 delay=60ms |
| 微博 | ProseMirror 富文本 | 逐字输入 delay=60ms |

## 自动化程度

| 环节 | 自动化 | 说明 |
|------|--------|------|
| PDF 诊断 | ✅ 自动 | `pdf_to_markdown.py --diagnose` |
| 文字型 PDF 提取 | ✅ 自动 | `pymupdf4llm` 直接转换 |
| 转曲 PDF 提取 | ❌ 需 Hermes AI | vision 逐页读图，需 AI 参与 |
| DOCX 提取 | ✅ 自动 | `docx_to_markdown.py` |
| Markdown → 各平台文案 | ✅ 自动 | `content_rewriter.py` |
| 发布到各平台 | ✅ 自动 | Playwright + CDP |

## 架构设计

所有平台发布器遵循统一接口：

```python
pub = PlatformPublisher()
pub.start()   # CDP 连接 Edge 浏览器
pub.publish(title, content, cover_image, tags)
pub.stop()
```

关键设计决策：
- **CDP 模式**：连接真实浏览器避免 `navigator.webdriver` 检测
- **Shadow DOM 劫持**：`add_init_script` 强制 `attachShadow({mode:'open'})`
- **持久化上下文**：`launch_persistent_context` 保存登录态
- **平台差异**：各平台 DOM/流程不同，独立维护选择器
- **`all` 命令**：一键同步发布到全部 6 个平台

## 安全警告

⚠️ **绝对不要上传以下文件到公开仓库：**

- `edge-profile/` — 浏览器配置文件，包含所有平台的登录 Cookies
- `.env` — 环境变量，可能包含凭据
- `chromium-browser-data/` — Chromium 浏览器数据
- `content/` — 从 PDF 生成的素材，含完整宣传内容

以上目录已加入 `.gitignore`。

⚠️ **封号风险（已发生）：**

- 今日头条账号在逐字输入功能测试中**已被永久封禁**。
- 所有字节系平台（头条、抖音）风控极其严格，请用小号测试。
- 详见顶部「⚠️ 封号风险警告」。

## 下一步计划

| 优先级 | 改进项 | 状态 |
|--------|--------|------|
| P0 | 中文输入改用 `keyboard.type()` 产生真实按键事件（替代 `insert_text`） | ✅ |
| P0 | 按键间隔改用对数正态分布（替代均匀分布） | ✅ |
| P1 | 模拟中文 IME 输入流程（compositionstart→compositionend） | ✅ |
| P1 | 随机切 tab / 失焦 / 选中重写等"分心"行为 | ✅ |
| P1 | 移除 playwright 依赖，只保留 patchright | ✅ |
| P2 | Canvas/WebGL 指纹混淆 | ✅ |
| P2 | WebRTC 禁用 | ✅ |
| P2 | HTTP Client Hints 伪装 | ✅ |
| P3 | 鼠标轨迹真实化（手抖噪声、过冲修正） | ⏳ |
| P3 | IP 代理轮换 | ⏳ |
| P3 | TLS 指纹对抗 | ⏳ |

## 反检测体系（已完成）

### 浏览器指纹
- `navigator.webdriver` → false
- `navigator.platform/plugins/languages/hardwareConcurrency/deviceMemory` 随机化
- `screen.*` / `window.devicePixelRatio` / `window.chrome.runtime` 补全

### 硬件指纹
- Canvas 指纹噪声（mulberry32 PRNG + RGB 像素扰动）
- WebGL VENDOR/RENDERER 伪造（3 套 NVIDIA/Intel/AMD 设备预设）
- AudioContext 指纹噪声

### 网络指纹
- WebRTC 完全禁用
- HTTP `Sec-CH-UA` / `Accept-Language` Client Hints 伪装
- 时区 + 语言一致性校验

### 行为指纹
- `keyboard.type()` 真实按键事件（keydown/keyup 序列）
- 按键间隔对数正态分布（中位数 25-67ms，含长尾）
- 波浪式打字速度（开头慢→中间快→结尾慢）
- 2% 概率打错删除模拟
- 中文 IME composition 事件注入
- 贝塞尔曲线鼠标轨迹
- `browse_before/browse_after` 浏览行为
- `distract_think` 走神停顿
- `distract_mouse_leave` 鼠标移出窗口
- `distract_edit_text` 选中重写
- `distract_post_fill` 填充后停留校对

## 参考资料

以下项目为本项目提供了灵感和思路：

- [anything-analyzer](https://github.com/Mouseww/anything-analyzer) — 全场景抓包 + AI 协议逆向工具，其 `fingerprint/` 模块（设备预设、stealth 脚本、HTTP 头伪装）是本项目 stealth.py 的直接参考来源
- [playwright-automation](https://github.com/iamtornado/playwright-automation) — Playwright 自动化示例集合，提供了 CDP 连接真实浏览器的基础架构思路
- [浏览器自动化反检测技术总结](https://yousali.com/posts/20260213-browser-automation-anti-detection/) — 浏览器自动化反检测技术综述，覆盖指纹伪装、行为模拟、CDP 检测等多个维度
