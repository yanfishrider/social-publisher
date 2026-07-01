# social-publisher

多平台社交媒体自动发布工具，基于 Playwright + CDP 连接真实浏览器，绕过反爬检测。

## 支持平台

| 平台 | 内容类型 | 反爬等级 | 状态 |
|------|----------|----------|------|
| 小红书 (Xiaohongshu) | 图文笔记 | Medium | ✅ |
| 百家号 (Baijiahao) | 长文 | High | ✅ |
| 今日头条 (Toutiao) | 长文 | Very High | ✅ |
| 搜狐号 (Sohu) | 长文 | Low | ⏳ |

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

## 项目结构

```
social-publisher/
├── main.py                # CLI 入口 (login + publish)
├── config.py              # 配置加载 (PublishConfig dataclass)
├── browser_manager.py     # 浏览器生命周期管理
├── image_utils.py         # PIL 图片压缩
├── platforms/
│   ├── xiaohongshu.py     # 小红书发布器
│   ├── baijiahao.py       # 百家号发布器
│   └── toutiao.py         # 今日头条发布器
├── pyproject.toml         # 项目元数据 + 依赖
├── .env.example           # 环境变量模板
└── article.md             # 示例文章
```

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

## 安全警告

⚠️ **绝对不要上传以下文件到公开仓库：**

- `edge-profile/` — 浏览器配置文件，包含所有平台的登录 Cookies
- `.env` — 环境变量，可能包含凭据
- `chromium-browser-data/` — Chromium 浏览器数据

以上目录已加入 `.gitignore`。

⚠️ **发布内容规范：**

- 严禁包含"自动化""测试""Playwright""Selenium"等敏感词（会被封号）
- 使用正常的技术文章或生活内容进行测试
