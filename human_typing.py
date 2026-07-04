"""
真人打字模拟 — 各平台差异化参数 + 随机抖动
消除"所有平台完全一致的打字模式"这个反爬指纹
"""
import random


# ── 平台差异化打字 profile ──

class TypingProfile:
    """打字行为参数范围"""
    def __init__(self, char_delay, para_pause, think_every, think_pause):
        self.char_delay = char_delay      # (min_ms, max_ms) 每字延迟
        self.para_pause = para_pause      # (min_ms, max_ms) 段落间停顿
        self.think_every = think_every    # (min, max) 每 N 段"思考"一次
        self.think_pause = think_pause    # (min_ms, max_ms) "思考"停顿时长


PROFILES = {
    # 字节跳动（抖音 + 头条）— 反爬最严：打字偏慢、停顿偏长
    "byte_dance": TypingProfile(
        char_delay=(50, 120),
        para_pause=(200, 800),
        think_every=(3, 7),
        think_pause=(500, 2000),
    ),
    # 百度百家号 — 反爬较高
    "baidu": TypingProfile(
        char_delay=(40, 100),
        para_pause=(150, 600),
        think_every=(4, 8),
        think_pause=(400, 1500),
    ),
    # 小红书 — 短内容，打字可以快一点
    "xhs": TypingProfile(
        char_delay=(15, 40),
        para_pause=(100, 400),
        think_every=(5, 10),
        think_pause=(300, 1000),
    ),
    # B站 / 微博 — 中等反爬
    "standard": TypingProfile(
        char_delay=(30, 80),
        para_pause=(100, 500),
        think_every=(5, 10),
        think_pause=(300, 1200),
    ),
}


def _r(range_tuple: tuple[int, int]) -> int:
    """从范围中取随机整数"""
    return random.randint(range_tuple[0], range_tuple[1])


def _char_delay(cfg: TypingProfile) -> int:
    """单字延迟：在 profile 范围内随机，约 3% 概率触发微卡顿 """
    delay = _r(cfg.char_delay)
    if random.random() < 0.03:
        delay += random.randint(100, 300)  # 偶尔手滑/想词
    return delay


# ── 鼠标移动模拟 ──

def human_move(page, locator) -> tuple[float, float]:
    """
    非直线轨迹移动鼠标到元素内随机位置。
    返回目标坐标 (tx, ty)，供后续坐标操作使用。
    """
    box = locator.bounding_box()
    if not box:
        return (0, 0)
    tx = box['x'] + box['width'] * random.uniform(0.2, 0.8)
    ty = box['y'] + box['height'] * random.uniform(0.2, 0.8)
    page.mouse.move(tx, ty, steps=random.randint(3, 8))
    page.wait_for_timeout(random.randint(50, 150))
    return (tx, ty)


def human_click(page, locator, force: bool = False, timeout: int | None = None):
    """模拟真人点击：先非直线移动鼠标到元素，稍停，再点击"""
    human_move(page, locator)
    locator.click(force=force, timeout=timeout)


# ── 公共 API ──

def human_type(page, content: str, profile: str = "standard"):
    """
    模拟真人逐字键入正文 — 每个字独立随机延迟。
    
    Args:
        page: Playwright Page 对象
        content: 要输入的内容
        profile: 平台 profile（byte_dance / baidu / xhs / standard）
    """
    cfg = PROFILES.get(profile, PROFILES["standard"])
    paragraphs = [p for p in content.split("\n") if p.strip()]
    total = len(paragraphs)
    next_think = random.randint(*cfg.think_every)

    for i, paragraph in enumerate(paragraphs):
        # 逐字独立随机延迟
        _type_chars(page, paragraph, cfg)

        # 段落间停顿
        if i < total - 1:
            page.wait_for_timeout(_r(cfg.para_pause))
            page.keyboard.press("Shift+Enter")
            page.wait_for_timeout(jitter(200))

        # 随机间隔的"思考"停顿
        if (i + 1) == next_think:
            page.wait_for_timeout(_r(cfg.think_pause))
            next_think = (i + 1) + random.randint(*cfg.think_every)


def human_type_on(page, locator, content: str, profile: str = "xhs"):
    """
    在指定 locator 上逐字输入（小红书等需要精确 locator 的平台）。
    每个字独立随机延迟。
    """
    cfg = PROFILES.get(profile, PROFILES["xhs"])
    paragraphs = [p for p in content.split("\n") if p.strip()]
    total = len(paragraphs)
    next_think = random.randint(*cfg.think_every)

    for i, paragraph in enumerate(paragraphs):
        _type_chars_on(page, locator, paragraph, cfg)

        if i < total - 1:
            page.wait_for_timeout(_r(cfg.para_pause))
            page.keyboard.press("Shift+Enter")
            page.wait_for_timeout(jitter(200))

        if (i + 1) == next_think:
            page.wait_for_timeout(_r(cfg.think_pause))
            next_think = (i + 1) + random.randint(*cfg.think_every)


def _type_chars(page, text: str, cfg: TypingProfile):
    """逐字键入 — 每个字独立随机延迟（page.keyboard 级别）"""
    for ch in text:
        page.keyboard.insert_text(ch)
        page.wait_for_timeout(_char_delay(cfg))


def _type_chars_on(page, locator, text: str, cfg: TypingProfile):
    """逐字键入 — 每个字独立随机延迟（locator 级别）"""
    for ch in text:
        page.keyboard.insert_text(ch)
        page.wait_for_timeout(_char_delay(cfg))


def jitter(base: int, pct: float = 0.3) -> int:
    """给固定值加 ±pct% 随机抖动"""
    return base + random.randint(-int(base * pct), int(base * pct))


def random_wait(page, base_ms: int, pct: float = 0.3):
    """固定等待 + 随机抖动的便捷方法"""
    page.wait_for_timeout(jitter(base_ms, pct))
