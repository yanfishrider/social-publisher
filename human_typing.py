"""
真人打字模拟 — keyboard.type() 真实按键 + 对数正态分布延迟
Patchright 的 keyboard.type() 产生真实 keydown/keyup 事件序列，替代 insert_text
"""
import random
import math


# ════════════════════════════════════════════════════════════════
# 对数正态分布（替代均匀分布）
# ════════════════════════════════════════════════════════════════

def _lognormal_delay(mu: float, sigma: float) -> int:
    """
    对数正态分布延迟。
    - mu=3.5, sigma=0.4 → 中位数 ~33ms，均值 ~36ms，长尾 ~150ms
    - mu=4.2, sigma=0.5 → 中位数 ~67ms，均值 ~76ms，长尾 ~300ms
    """
    val = random.lognormvariate(mu, sigma)
    return max(5, min(int(val), 500))  # 夹在 5~500ms


# ════════════════════════════════════════════════════════════════
# 平台差异化打字 Profile
# ════════════════════════════════════════════════════════════════

class TypingProfile:
    """打字行为参数"""
    def __init__(self, mu: float, sigma: float,
                 para_pause: tuple[int, int],
                 think_every: tuple[int, int],
                 think_pause: tuple[int, int]):
        self.mu = mu                  # 对数正态 μ
        self.sigma = sigma            # 对数正态 σ
        self.para_pause = para_pause  # 段落间停顿 (min, max) ms
        self.think_every = think_every  # 每 N 段"思考"一次
        self.think_pause = think_pause  # "思考"停顿时长 (min, max) ms


PROFILES = {
    "byte_dance": TypingProfile(
        mu=4.2, sigma=0.5,          # 慢速：中位数 ~67ms
        para_pause=(200, 800),
        think_every=(3, 7),
        think_pause=(500, 2000),
    ),
    "baidu": TypingProfile(
        mu=3.9, sigma=0.45,         # 中速：中位数 ~49ms
        para_pause=(150, 600),
        think_every=(4, 8),
        think_pause=(400, 1500),
    ),
    "xhs": TypingProfile(
        mu=3.2, sigma=0.35,         # 较快：中位数 ~25ms
        para_pause=(100, 400),
        think_every=(5, 10),
        think_pause=(300, 1000),
    ),
    "standard": TypingProfile(
        mu=3.6, sigma=0.4,          # 标准：中位数 ~37ms
        para_pause=(100, 500),
        think_every=(5, 10),
        think_pause=(300, 1200),
    ),
}


def _ri(rng: tuple[int, int]) -> int:
    return random.randint(rng[0], rng[1])


# ════════════════════════════════════════════════════════════════
# 打字速度韵律（波浪式）
# ════════════════════════════════════════════════════════════════

def _speed_wave(i: int, total: int) -> float:
    """
    模拟打字速度波浪：开头慢→中间快→结尾慢。
    返回速度倍率 0.7 ~ 1.5
    """
    progress = i / max(total, 1)
    wave = 1.0 + 0.3 * math.sin(progress * math.pi * 3)
    if progress > 0.85:
        wave += (progress - 0.85) * 2.0
    return max(0.7, min(1.5, wave))


# ════════════════════════════════════════════════════════════════
# 打错删除模拟
# ════════════════════════════════════════════════════════════════

def _maybe_typo() -> bool:
    return random.random() < 0.02


_SIMILAR_KEYS = {
    'a': 's', 's': 'a', 'd': 'f', 'f': 'd', 'g': 'h', 'h': 'g',
    'j': 'k', 'k': 'j', 'l': 'k', 'q': 'w', 'w': 'q', 'e': 'r',
    'r': 'e', 't': 'y', 'y': 't', 'u': 'i', 'i': 'u', 'o': 'p',
    'p': 'o', 'z': 'x', 'x': 'z', 'c': 'v', 'v': 'c', 'b': 'n',
    'n': 'b', 'm': 'n',
    '，': '。', '。': '，', '的': '地', '地': '的', '是': '时', '了': '啦',
}


def _similar_key(ch: str) -> str:
    return _SIMILAR_KEYS.get(ch, ch)


# ════════════════════════════════════════════════════════════════
# 公共 API — 真实按键版本
# ════════════════════════════════════════════════════════════════

def human_type(page, content: str, profile: str = "standard"):
    """
    模拟真人逐字键入 — 使用 keyboard.type() 产生真实 keydown/keyup 事件。
    按 \n 分段，段间用 Enter 换行。
    """
    cfg = PROFILES.get(profile, PROFILES["standard"])
    paragraphs = [p for p in content.replace("\r\n", "\n").split("\n")]
    total = len(paragraphs)
    next_think = random.randint(*cfg.think_every)

    for i, paragraph in enumerate(paragraphs):
        if not paragraph.strip():
            page.keyboard.press("Enter")
            page.wait_for_timeout(jitter(200))
            continue

        _type_paragraph(page, paragraph, cfg)

        if i < total - 1:
            page.wait_for_timeout(_ri(cfg.para_pause))
            page.keyboard.press("Enter")
            page.wait_for_timeout(jitter(200))

        if (i + 1) == next_think:
            page.wait_for_timeout(_ri(cfg.think_pause))
            next_think = (i + 1) + random.randint(*cfg.think_every)


def _type_paragraph(page, text: str, cfg: TypingProfile):
    """逐字键入段落"""
    _type_chars(page, text, cfg)


def _type_paragraph_on(page, locator, text: str, cfg: TypingProfile):
    """locator 版逐字键入（先聚焦元素）"""
    locator.focus()
    page.wait_for_timeout(jitter(200))
    _type_chars(page, text, cfg)


def _type_chars(page, text: str, cfg: TypingProfile):
    """逐字键入公共实现 — keyboard.type() + 对数正态延迟 + 打错删除"""
    for ch in text:
        # 中文输入法模拟：先发 composition 事件
        if _is_cjk(ch):
            _emit_ime(page, ch)

        if _maybe_typo():
            wrong = _similar_key(ch)
            page.keyboard.type(wrong, delay=_lognormal_delay(cfg.mu * 0.8, cfg.sigma))
            page.wait_for_timeout(random.randint(100, 300))
            page.keyboard.press("Backspace")
            page.wait_for_timeout(random.randint(80, 200))

        page.keyboard.type(ch, delay=_lognormal_delay(cfg.mu, cfg.sigma))


# ════════════════════════════════════════════════════════════════
# IME 输入法事件模拟
# ════════════════════════════════════════════════════════════════

def _is_cjk(ch: str) -> bool:
    """判断是否为 CJK 字符（中文/日文/韩文）"""
    cp = ord(ch)
    return (
        0x4E00 <= cp <= 0x9FFF   # CJK Unified Ideographs
        or 0x3400 <= cp <= 0x4DBF  # CJK Extension A
        or 0x20000 <= cp <= 0x2A6DF  # CJK Extension B
        or 0xF900 <= cp <= 0xFAFF  # CJK Compatibility
        or 0x3000 <= cp <= 0x303F  # CJK Symbols/Punctuation
        or 0xFF00 <= cp <= 0xFFEF  # Halfwidth/Fullwidth Forms
    )


def _emit_ime(page, ch: str):
    """
    模拟中文输入法的 composition 事件序列。
    通过 page.evaluate() 在焦点元素上手动派发。
    """
    pinyin = _char_to_pinyin(ch)
    try:
        page.evaluate(f"""
            (() => {{
                const el = document.activeElement || document.body;
                el.dispatchEvent(new CompositionEvent('compositionstart', {{
                    data: '{pinyin}', bubbles: true
                }}));
                el.dispatchEvent(new CompositionEvent('compositionupdate', {{
                    data: '{pinyin}', bubbles: true
                }}));
                // compositionend 在字符输入后由浏览器自然触发
            }})();
        """)
    except Exception:
        pass


def _char_to_pinyin(ch: str) -> str:
    """返回字符的模拟拼音（不需要准确，只需有数据）"""
    # 不需要真实的拼音映射，只要每次不同即可
    import hashlib
    h = hashlib.md5(ch.encode()).hexdigest()[:4]
    consonants = ['n', 'h', 'sh', 'zh', 'b', 'p', 'm', 'f', 'd', 't', 'l', 'g', 'k', 'j', 'q', 'x', 'r', 'z', 'c', 's', 'y', 'w']
    vowels = ['i', 'a', 'o', 'e', 'u', 'ao', 'ai', 'ei', 'ou', 'iu', 'ie', 'ue', 'an', 'en', 'in', 'ang', 'eng', 'ing', 'ong']
    c_idx = int(h[0:2], 16) % len(consonants)
    v_idx = int(h[2:4], 16) % len(vowels)
    return consonants[c_idx] + vowels[v_idx]


# ════════════════════════════════════════════════════════════════
# 针对 contenteditable / 特殊编辑器的版本
# ════════════════════════════════════════════════════════════════

def human_type_on(page, locator, content: str, profile: str = "xhs"):
    """
    在指定 locator 上逐字输入。
    按 \n 分段，段间用 Enter 换行。
    """
    cfg = PROFILES.get(profile, PROFILES["xhs"])
    # 按换行分段，保留非空行
    paragraphs = [p for p in content.replace("\r\n", "\n").split("\n")]
    total = len(paragraphs)
    next_think = random.randint(*cfg.think_every)

    for i, paragraph in enumerate(paragraphs):
        if not paragraph.strip():
            # 空行 → 多按一次 Enter（段落间距）
            page.keyboard.press("Enter")
            page.wait_for_timeout(jitter(200))
            continue

        _type_paragraph_on(page, locator, paragraph, cfg)

        if i < total - 1:
            page.wait_for_timeout(_ri(cfg.para_pause))
            page.keyboard.press("Enter")
            page.wait_for_timeout(jitter(200))

        if (i + 1) == next_think:
            page.wait_for_timeout(_ri(cfg.think_pause))
            next_think = (i + 1) + random.randint(*cfg.think_every)



# ════════════════════════════════════════════════════════════════
# 鼠标相关（保持不变）
# ════════════════════════════════════════════════════════════════

def _bezier_point(t: float, p0, p1, p2, p3) -> tuple[float, float]:
    u = 1 - t
    x = u**3 * p0[0] + 3*u**2*t * p1[0] + 3*u*t**2 * p2[0] + t**3 * p3[0]
    y = u**3 * p0[1] + 3*u**2*t * p1[1] + 3*u*t**2 * p2[1] + t**3 * p3[1]
    return (x, y)


def human_move(page, locator) -> tuple[float, float]:
    """
    贝塞尔曲线 + 手抖噪声 + 过冲修正。
    模拟真人鼠标移动的微颤和不精确性。
    """
    box = locator.bounding_box()
    if not box:
        return (0, 0)

    tx = box['x'] + box['width'] * random.uniform(0.2, 0.8)
    ty = box['y'] + box['height'] * random.uniform(0.2, 0.8)

    try:
        vp = page.viewport_size or {"width": 1920, "height": 1080}
    except Exception:
        vp = {"width": 1920, "height": 1080}
    sx = random.randint(100, vp["width"] - 100)
    sy = random.randint(100, vp["height"] - 200)

    cp1x = sx + (tx - sx) * random.uniform(0.3, 0.5) + random.randint(-80, 80)
    cp1y = sy + (ty - sy) * random.uniform(0.1, 0.3) + random.randint(-60, 60)
    cp2x = sx + (tx - sx) * random.uniform(0.6, 0.8) + random.randint(-50, 50)
    cp2y = sy + (ty - sy) * random.uniform(0.5, 0.7) + random.randint(-40, 40)

    # 过冲：约 60% 概率轻微超出目标再拉回
    overshoot = random.random() < 0.6
    if overshoot:
        overshoot_dist = random.randint(5, 15)
        angle = math.atan2(ty - sy, tx - sx)
        ox = tx + math.cos(angle) * overshoot_dist
        oy = ty + math.sin(angle) * overshoot_dist
    else:
        ox, oy = tx, ty

    steps = random.randint(20, 40)
    for i in range(steps + 1):
        t = i / steps

        # 贝塞尔基础位置
        bx, by = _bezier_point(t, (sx, sy), (cp1x, cp1y), (cp2x, cp2y), (ox, oy))

        # 手抖噪声：高频低幅，接近目标时振幅增大（紧张）
        progress = t
        tremor_amp = 1.0 + progress * 1.5  # 越接近目标抖动越大
        noise_x = (random.random() - 0.5) * 2 * tremor_amp
        noise_y = (random.random() - 0.5) * 2 * tremor_amp

        page.mouse.move(bx + noise_x, by + noise_y)
        page.wait_for_timeout(random.randint(5, 12))

    # 过冲后拉回
    if overshoot:
        page.wait_for_timeout(random.randint(40, 100))
        # 拉回过程也用微颤
        pullback_steps = random.randint(5, 10)
        for i in range(pullback_steps + 1):
            t = i / pullback_steps
            px = ox + (tx - ox) * t
            py = oy + (ty - oy) * t
            noise_x = (random.random() - 0.5) * 1.5
            noise_y = (random.random() - 0.5) * 1.5
            page.mouse.move(px + noise_x, py + noise_y)
            page.wait_for_timeout(random.randint(3, 8))

    page.wait_for_timeout(random.randint(30, 80))
    return (tx, ty)


def human_click(page, locator, force=False, timeout=None):
    human_move(page, locator)
    locator.click(force=force, timeout=timeout)


def jitter(base: int, pct: float = 0.3) -> int:
    return base + random.randint(-int(base * pct), int(base * pct))
