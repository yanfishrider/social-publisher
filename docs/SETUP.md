# social-publisher 新电脑搭建指南

## 前置条件

- Windows 10/11
- Edge 浏览器
- Python 3.11+ + uv 包管理器
- Git

## 1. 克隆项目

```bash
cd D:\PyCharm\PythonFile
git clone git@github.com:yanfishrider/social-publisher.git
cd social-publisher
uv sync
```

## 2. Edge CDP 启动脚本

保存为桌面 `启动CDP浏览器.bat`：

```batch
@echo off
echo 正在关闭已有 Edge 进程...
taskkill //F //IM msedge.exe >nul 2>&1
timeout /t 2 /nobreak >nul
echo 启动 Edge CDP (端口 9222)...
start msedge.exe --remote-debugging-port=9222 --no-first-run --user-data-dir="%USERPROFILE%\AppData\Local\Temp\edge-cdp" about:blank
echo.
echo Edge CDP 已启动 (端口 9222)
echo.
pause
```

## 3. 首次启动流程

```bash
# 1. 双击桌面 启动CDP浏览器.bat
# 2. 在弹出的 Edge 窗口中手动登录各平台（只需一次）
#    - 小红书: https://creator.xiaohongshu.com/
#    - 百家号: https://baijiahao.baidu.com/
#    - 头条号: https://mp.toutiao.com/
#    - B站: https://member.bilibili.com/
#    - 抖音: https://creator.douyin.com/
#    - 微博: https://weibo.com/

# 3. 启动 Web 界面
cd D:\PyCharm\PythonFile\social-publisher
uv run uvicorn server:app --reload --port 8085

# 4. 浏览器打开 http://127.0.0.1:8085/
```

## 4. 端口说明

| 端口 | 用途 |
|------|------|
| 9222 | Edge CDP 调试端口（bat 脚本启动） |
| 8085 | social-publisher Web 界面（uvicorn） |

## 5. 注意事项

- Edge CDP 窗口不要关闭（最小化即可）
- 登录态保存在 `%USERPROFILE%\AppData\Local\Temp\edge-cdp`（临时目录，重启电脑会清）
- 如需持久化登录，改 bat 中的 `--user-data-dir` 为持久路径如 `D:\edge-profile`
