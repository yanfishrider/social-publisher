# social-publisher

多平台社交媒体自动发布工具，基于 Playwright + CDP 连接真实浏览器，绕过反爬检测。

支持从 PDF 宣传册一键生成多平台适配文案并自动发布。

## 支持平台

| 平台 | 内容类型 | 反爬等级 | 状态 |
|------|----------|----------|------|
| 小红书 (Xiaohongshu) | 图文笔记 | Medium | ✅ |
| 百家号 (Baijiahao) | 长文 | High | ✅ |
| 今日头条 (Toutiao) | 长文 | Very High | ✅ |
| B站专栏 (Bilibili) | 专栏文章 | Medium | ✅ |
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
# 登录完成后按 Enter 关闭

# 4. 发布内容（使用 CDP 连接模式，--use-edge 绕过反爬）
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
| 小红书 | `content_rewriter.py` 精简为 ~800 字短文案 | --content-file 且 >500 字 |
| 百家号 | `content_rewriter.py` 转为纯文本段落 | --content-file 且 >2000 字 |
| 头条号 | `content_rewriter.py` 转为纯文本段落 | --content-file 且 >2000 字 |

使用 `--content-text` 直传短文本则跳过自动改写。

```bash
# 三平台一键发布（使用同一份 content/*.md）
uv run python main.py publish xiaohongshu --use-edge \
  --title "标题" --content-file content/xxx.md --cover-image content/xxx.png

uv run python main.py publish baijiahao --use-edge \
  --title "标题" --content-file content/xxx.md --cover-image content/xxx.png

uv run python main.py publish toutiao --use-edge \
  --title "标题" --content-file content/xxx.md --cover-image content/xxx.png
```

## 项目结构

```
social-publisher/
├── main.py                  # CLI 入口 (login + publish)
├── config.py                # 配置加载 (PublishConfig dataclass)
├── browser_manager.py       # 浏览器生命周期管理
├── image_utils.py           # PIL 图片压缩
├── pdf_to_markdown.py       # PDF → Markdown 转换工具
├── content_rewriter.py      # 内容改写（适配各平台格式）
├── content/                 # 内容素材（从 PDF 生成，不推送）
│   ├── xxx.md               #   从 PDF 提取的 Markdown
│   └── xxx.png              #   封面图
├── platforms/
│   ├── xiaohongshu.py       # 小红书发布器
│   ├── baijiahao.py         # 百家号发布器
│   └── toutiao.py           # 今日头条发布器
├── pyproject.toml           # 项目元数据 + 依赖
├── .env.example             # 环境变量模板
└── README.md
```

## 自动化程度

| 环节 | 自动化 | 说明 |
|------|--------|------|
| PDF 诊断 | ✅ 自动 | `pdf_to_markdown.py --diagnose` |
| 文字型 PDF 提取 | ✅ 自动 | `pymupdf4llm` 直接转换 |
| 转曲 PDF 提取 | ❌ 需 Hermes AI | vision 逐页读图，需 AI 参与 |
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
- **长文本优化**：百家号 >1000 字自动切换剪贴板粘贴，避免逐字键入超时

## 安全警告

⚠️ **绝对不要上传以下文件到公开仓库：**

- `edge-profile/` — 浏览器配置文件，包含所有平台的登录 Cookies
- `.env` — 环境变量，可能包含凭据
- `chromium-browser-data/` — Chromium 浏览器数据
- `content/` — 从 PDF 生成的素材，含完整宣传内容

以上目录已加入 `.gitignore`。

⚠️ **发布内容规范：**

- 严禁包含"自动化""测试""Playwright""Selenium"等敏感词（会被封号）
- 使用正常的技术文章或生活内容进行测试
