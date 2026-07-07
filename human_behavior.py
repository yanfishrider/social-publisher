"""
分心行为模拟 — 填充过程中和填充后的"人味"动作
消除"打开页面一口气填完"的机器人特征
"""
import random
import math


def distract_think(page, duration_ms: int = None):
    """
    模拟走神：停顿 + 鼠标无目的移动 + 微滚动。
    在段与段之间调用。
    """
    if duration_ms is None:
        duration_ms = random.randint(2000, 8000)

    vp = _viewport(page)
    elapsed = 0

    # 随机停顿
    pause = random.randint(800, min(duration_ms, 3000))
    page.wait_for_timeout(pause)
    elapsed += pause

    # 鼠标无目的移动
    if elapsed < duration_ms:
        for _ in range(random.randint(1, 3)):
            tx = random.randint(100, vp["width"] - 100)
            ty = random.randint(100, vp["height"] - 200)
            page.mouse.move(tx, ty, steps=random.randint(5, 15))
            page.wait_for_timeout(random.randint(300, 800))
            elapsed += 500

    # 微滚动
    if elapsed < duration_ms:
        page.mouse.wheel(0, random.randint(-100, 100))
        page.wait_for_timeout(random.randint(200, 500))

    # 剩余时间
    remaining = duration_ms - elapsed
    if remaining > 0:
        page.wait_for_timeout(remaining)


def distract_mouse_leave(page):
    """
    鼠标移出浏览器窗口（模拟看手机/喝水/分心）。
    约 30% 概率触发。
    """
    if random.random() > 0.3:
        return
    vp = _viewport(page)
    # 移动到屏幕边缘
    edge_x = random.choice([-50, vp["width"] + 50])
    edge_y = random.randint(0, vp["height"])
    page.mouse.move(edge_x, edge_y, steps=random.randint(10, 25))
    page.wait_for_timeout(random.randint(1500, 5000))
    # 鼠标移回来
    back_x = random.randint(200, vp["width"] - 200)
    back_y = random.randint(100, vp["height"] - 200)
    page.mouse.move(back_x, back_y, steps=random.randint(8, 20))
    page.wait_for_timeout(random.randint(300, 800))


def distract_edit_text(page, locator=None):
    """
    模拟修改：选中一段文字 → 删除 → 重写（模拟不满意修改）。
    约 15% 概率触发。
    """
    if random.random() > 0.15:
        return

    try:
        # 选中最后几个字
        if locator:
            locator.focus()
        page.keyboard.press("End")
        page.wait_for_timeout(random.randint(100, 300))

        # Shift+Home 或 Shift+Left 选中
        select_count = random.randint(3, 10)
        for _ in range(select_count):
            page.keyboard.press("Shift+ArrowLeft")
            page.wait_for_timeout(random.randint(30, 80))

        page.wait_for_timeout(random.randint(500, 1500))
        page.keyboard.press("Backspace")
        page.wait_for_timeout(random.randint(200, 600))

        # 重写几个字
        rewrite = random.choice(["确实", "真的", "非常", "特别", "相当", "十分", "尤其"])
        page.keyboard.type(rewrite, delay=random.randint(30, 80))
        page.wait_for_timeout(random.randint(300, 800))
    except Exception:
        pass


def distract_post_fill(page, duration_ms: int = None):
    """
    填充后停留：滚动检查 + 停顿思考（模拟校对）。
    在 browse_after 之后、点击发布之前调用。
    """
    if duration_ms is None:
        duration_ms = random.randint(4000, 12000)

    vp = _viewport(page)
    elapsed = 0

    # 重新滚动到顶部
    for _ in range(random.randint(3, 6)):
        page.mouse.wheel(0, -random.randint(100, 300))
        page.wait_for_timeout(random.randint(200, 500))
        elapsed += 400

    # 逐段慢慢往下看
    for _ in range(random.randint(4, 8)):
        page.mouse.wheel(0, random.randint(80, 250))
        page.wait_for_timeout(random.randint(600, 2000))
        elapsed += 1200
        if elapsed > duration_ms:
            break

    # 鼠标随机悬停（假装在读某处）
    for _ in range(random.randint(1, 3)):
        tx = random.randint(200, vp["width"] - 200)
        ty = random.randint(200, vp["height"] - 200)
        page.mouse.move(tx, ty, steps=random.randint(5, 12))
        page.wait_for_timeout(random.randint(800, 2500))
        elapsed += 1500
        if elapsed > duration_ms:
            break

    remaining = duration_ms - elapsed
    if remaining > 0:
        page.wait_for_timeout(remaining)


def _viewport(page) -> dict:
    try:
        vp = page.viewport_size
        if vp:
            return vp
    except Exception:
        pass
    return {"width": 1920, "height": 1080}
