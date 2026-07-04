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
    """单字延迟：在 profile 范围内随机，约 3% 概率触发微卡顿"""
    delay = _r(cfg.char_delay)
    if random.random() < 0.03:
        delay += random.randint(100, 300)  # 偶尔手滑/想词
    return delay


# ── 打字速度韵律 ──

def _speed_wave(i: int, total: int) -> float:
    """
    模拟打字速度的波浪式变化：开始慢（找节奏）、中间快、结尾又慢。
    返回速度倍率 (0.7 ~ 1.5)，乘以基础延迟。
    """
    progress = i / max(total, 1)
    # 正弦波 + 线性减速尾部
    wave = 1.0 + 0.3 * (__import__("math").sin(progress * __import__("math").pi * 3))
    # 最后 15% 减速
    if progress > 0.85:
        wave += (progress - 0.85) * 2.0
    return max(0.7, min(1.5, wave))


# ── 打错删除模拟 ──

def _maybe_typo() -> bool:
    """约 2% 概率触发打错"""
    return random.random() < 0.02


# ── 鼠标贝塞尔曲线 ──

def _bezier_point(t: float, p0, p1, p2, p3) -> tuple[float, float]:
    """三次贝塞尔曲线上的点"""
    u = 1 - t
    x = u**3 * p0[0] + 3*u**2*t * p1[0] + 3*u*t**2 * p2[0] + t**3 * p3[0]
    y = u**3 * p0[1] + 3*u**2*t * p1[1] + 3*u*t**2 * p2[1] + t**3 * p3[1]
    return (x, y)


# ── 鼠标移动模拟 ──

def human_move(page, locator) -> tuple[float, float]:
    """
    贝塞尔曲线轨迹移动鼠标到元素内随机位置。
    返回目标坐标 (tx, ty)。
    """
    box = locator.bounding_box()
    if not box:
        return (0, 0)
    
    # 目标：元素内随机位置
    tx = box['x'] + box['width'] * random.uniform(0.2, 0.8)
    ty = box['y'] + box['height'] * random.uniform(0.2, 0.8)
    
    # 起点：当前鼠标位置或随机起点
    try:
        vp = page.viewport_size or {"width": 1920, "height": 1080}
    except Exception:
        vp = {"width": 1920, "height": 1080}
    sx = random.randint(100, vp["width"] - 100)
    sy = random.randint(100, vp["height"] - 200)
    
    # 贝塞尔控制点：偏向目标方向加随机偏移
    cp1x = sx + (tx - sx) * random.uniform(0.3, 0.5) + random.randint(-80, 80)
    cp1y = sy + (ty - sy) * random.uniform(0.1, 0.3) + random.randint(-60, 60)
    cp2x = sx + (tx - sx) * random.uniform(0.6, 0.8) + random.randint(-50, 50)
    cp2y = sy + (ty - sy) * random.uniform(0.5, 0.7) + random.randint(-40, 40)
    
    steps = random.randint(15, 30)
    for i in range(steps + 1):
        t = i / steps
        x, y = _bezier_point(t, (sx, sy), (cp1x, cp1y), (cp2x, cp2y), (tx, ty))
        page.mouse.move(x, y)
        page.wait_for_timeout(random.randint(5, 15))
    
    page.wait_for_timeout(random.randint(30, 80))
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
    """逐字键入 — 波浪式速度 + 随机打错删除"""
    total = len(text)
    for i, ch in enumerate(text):
        # 速度韵律：波浪式快慢变化
        wave = _speed_wave(i, total)
        base_delay = _char_delay(cfg)
        delay = int(base_delay * wave)
        
        # 打错删除模拟
        if _maybe_typo():
            # 敲一个错字
            wrong = _similar_key(ch)
            page.keyboard.insert_text(wrong)
            page.wait_for_timeout(random.randint(100, 300))
            page.keyboard.press("Backspace")
            page.wait_for_timeout(random.randint(80, 200))
        
        page.keyboard.insert_text(ch)
        page.wait_for_timeout(delay)


def _similar_key(ch: str) -> str:
    """返回一个相近的键（模拟打错）"""
    nearby = {
        'a': 's', 's': 'a', 'd': 'f', 'f': 'd', 'g': 'h', 'h': 'g',
        'j': 'k', 'k': 'j', 'l': 'k', 'q': 'w', 'w': 'q', 'e': 'r',
        'r': 'e', 't': 'y', 'y': 't', 'u': 'i', 'i': 'u', 'o': 'p',
        'p': 'o', 'z': 'x', 'x': 'z', 'c': 'v', 'v': 'c', 'b': 'n',
        'n': 'b', 'm': 'n', '1': '2', '2': '1', '3': '4', '4': '3',
        '，': '。', '。': '，', '的': '地', '地': '的', '是': '时', '了': '啦',
    }
    return nearby.get(ch, ch)


def _type_chars_on(page, locator, text: str, cfg: TypingProfile):
    """逐字键入 — 波浪式速度 + 随机打错删除（locator 版本）"""
    total = len(text)
    for i, ch in enumerate(text):
        wave = _speed_wave(i, total)
        base_delay = _char_delay(cfg)
        delay = int(base_delay * wave)
        
        if _maybe_typo():
            wrong = _similar_key(ch)
            page.keyboard.insert_text(wrong)
            page.wait_for_timeout(random.randint(100, 300))
            page.keyboard.press("Backspace")
            page.wait_for_timeout(random.randint(80, 200))
        
        page.keyboard.insert_text(ch)
        page.wait_for_timeout(delay)


def jitter(base: int, pct: float = 0.3) -> int:
    """给固定值加 ±pct% 随机抖动"""
    return base + random.randint(-int(base * pct), int(base * pct))


def random_wait(page, base_ms: int, pct: float = 0.3):
    """固定等待 + 随机抖动的便捷方法"""
    page.wait_for_timeout(jitter(base_ms, pct))
