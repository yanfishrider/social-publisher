"""
频率控制 — 记录发布历史，防止短时间内高频发布触发风控
"""
import json
import time
import os
from pathlib import Path
from datetime import datetime, timedelta

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "publish_history.json")

# 默认限制
DEFAULT_MAX_PER_DAY = 3        # 单平台每天最多发布数
DEFAULT_MIN_INTERVAL = 300     # 同平台两次发布最短间隔（秒）
DEFAULT_COOLDOWN_MINUTES = 30  # 触发限制后的冷却时间（分钟）


def _load() -> dict:
    """加载发布历史"""
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save(data: dict):
    """保存发布历史"""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def can_publish(platform: str, max_per_day: int = DEFAULT_MAX_PER_DAY,
                min_interval: int = DEFAULT_MIN_INTERVAL) -> tuple[bool, str]:
    """
    检查是否可以发布。
    返回 (是否允许, 原因)。
    """
    data = _load()
    now = time.time()
    today = datetime.now().strftime("%Y-%m-%d")
    
    records = data.get(platform, [])
    
    # 清理过期记录（保留 3 天）
    cutoff = now - 3 * 86400
    records = [r for r in records if r["ts"] > cutoff]
    
    # 今天已发数量
    today_count = sum(1 for r in records
                      if datetime.fromtimestamp(r["ts"]).strftime("%Y-%m-%d") == today)
    
    if today_count >= max_per_day:
        return False, f"今日已达上限 ({today_count}/{max_per_day})"
    
    # 检查最短间隔
    if records:
        last_ts = records[-1]["ts"]
        elapsed = now - last_ts
        if elapsed < min_interval:
            remain = int(min_interval - elapsed)
            return False, f"距上次发布仅 {int(elapsed)}s，需等 {remain}s"
    
    return True, "ok"


def record(platform: str, title: str = "", success: bool = True):
    """
    记录一次发布。
    在发布完成后调用。
    """
    data = _load()
    
    if platform not in data:
        data[platform] = []
    
    data[platform].append({
        "ts": time.time(),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "title": title[:30],
        "success": success,
    })
    
    # 只保留最近 50 条
    if len(data[platform]) > 50:
        data[platform] = data[platform][-50:]
    
    _save(data)


def get_stats(platform: str | None = None) -> dict:
    """获取发布统计"""
    data = _load()
    today = datetime.now().strftime("%Y-%m-%d")
    
    def platform_stats(p):
        records = data.get(p, [])
        today_count = sum(1 for r in records
                         if datetime.fromtimestamp(r["ts"]).strftime("%Y-%m-%d") == today)
        last = records[-1] if records else None
        return {
            "today": today_count,
            "total": len(records),
            "last": last["time"] if last else None,
        }
    
    if platform:
        return {platform: platform_stats(platform)}
    
    return {p: platform_stats(p) for p in data}
