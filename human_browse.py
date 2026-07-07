"""
真人浏览行为模拟 — 发布前后的"阅读"动作
消除"打开页面直接填内容"的机器人特征
"""
import random


def browse_before(page):
    """
    发布前浏览：模拟看规则、看模板、犹豫一下。
    在填写内容之前调用。
    """
    page.wait_for_timeout(random.randint(3000, 6000))

    # 1. 随机滚动页面（假装浏览发布规则/提示）
    for _ in range(random.randint(2, 4)):
        delta = random.randint(100, 400)
        page.mouse.wheel(0, delta)
        page.wait_for_timeout(random.randint(400, 1200))

    # 2. 悬停某个区域（假装阅读）
    vp = page.viewport_size or {"width": 1920, "height": 1080}
    hx = random.randint(100, vp["width"] - 100)
    hy = random.randint(200, vp["height"] - 300)
    page.mouse.move(hx, hy)
    page.wait_for_timeout(random.randint(500, 1500))

    # 3. 再滚一下
    for _ in range(random.randint(1, 3)):
        delta = random.randint(-200, 200)
        page.mouse.wheel(0, delta)
        page.wait_for_timeout(random.randint(300, 800))


def browse_after(page):
    """
    发布后校对：模拟上下滚动检查内容。
    在填写完内容后、点击发布前调用。
    """
    page.wait_for_timeout(random.randint(500, 1500))

    # 向上滚动（假装从头检查）
    for _ in range(random.randint(3, 6)):
        page.mouse.wheel(0, -random.randint(100, 300))
        page.wait_for_timeout(random.randint(200, 600))

    # 向下滚动（假装再扫一遍）
    for _ in range(random.randint(3, 6)):
        page.mouse.wheel(0, random.randint(100, 300))
        page.wait_for_timeout(random.randint(200, 600))

    # 末尾停顿（假装思考）
    page.wait_for_timeout(random.randint(800, 2000))


def random_hover(page, locator=None):
    """
    在页面上随机位置悬停，模拟注意力分散。
    可选：悬停在指定元素上。
    """
    if locator:
        box = locator.bounding_box()
        if box:
            tx = box['x'] + box['width'] * random.uniform(0.3, 0.7)
            ty = box['y'] + box['height'] * random.uniform(0.3, 0.7)
            page.mouse.move(tx, ty)
            page.wait_for_timeout(random.randint(300, 1000))
            return

    vp = page.viewport_size or {"width": 1920, "height": 1080}
    page.mouse.move(
        random.randint(100, vp["width"] - 100),
        random.randint(100, vp["height"] - 200),
    )
    page.wait_for_timeout(random.randint(300, 800))
