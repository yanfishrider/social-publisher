"""
内容改写模块 — 将原始素材改写为各平台适配的文案

小红书：标题 ≤20字，正文 ~1000字，短段落，无 emoji
百家号/头条号：支持长文，去 Markdown 格式，保留完整结构
"""

import re


# ── 公共工具 ──────────────────────────────────────────

def _strip_markdown(text: str) -> str:
    """清除行内 Markdown 语法"""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-*+]\s+", "", text, flags=re.MULTILINE)
    return text


def _extract_tags(text: str) -> list[str]:
    """从文本中提取合适的标签"""
    tag_map = {
        "K12": "K12教育", "小升初": "小升初", "初升高": "初升高",
        "国际": "国际教育", "留学": "留学规划", "托福": "托福备考",
        "SAT": "SAT", "奥数": "奥数", "重庆": "重庆升学",
        "牛津": "名校师资", "曼大": "曼大优学", "保录取": "名校保录取",
    }
    tags = []
    text_lower = text.lower()
    for keyword, tag in tag_map.items():
        if keyword.lower() in text_lower and tag not in tags:
            tags.append(tag)
    return tags[:5]


def _extract_highlights(text: str) -> list[str]:
    """提取百分比、数字等亮点数据"""
    patterns = [
        r"(上岸率[高达]*[0-9.]+%[^，。\n]*)",
        r"([0-9]+年[^，。\n]*深耕[^，。\n]*)",
        r"([0-9]+家校区[^，。\n]*)",
        r"([0-9]+人[^，。\n]*(?:保送|上岸|成功)[^，。\n]*)",
    ]
    highlights, seen = [], set()
    for pat in patterns:
        for m in re.findall(pat, text):
            m = m.strip()
            if m not in seen and len(m) < 50:
                seen.add(m)
                highlights.append(f"  - {m}")
    return highlights[:5]


# ── 小红书改写 ────────────────────────────────────────

def rewrite_for_xhs(md_text: str, base_title: str = "") -> dict:
    """
    从小红书风格精简文案。

    返回: {"title": str, "body": str, "tags": list[str]}
    """
    sections = _parse_sections(md_text)
    body = _build_xhs_body(sections)
    title = _xhs_title(base_title, sections)
    tags = _extract_tags(md_text)
    return {"title": title, "body": body, "tags": tags}


def _parse_sections(text: str) -> list[dict]:
    """按 ## 二级标题分段，提取标题和正文片段"""
    result = []
    blocks = re.split(r"\n## ", text)
    for block in blocks[1:]:
        lines = block.strip().split("\n")
        heading = lines[0].strip().rstrip("：:")
        body_parts = []
        for l in lines[1:]:
            l = l.strip()
            # 跳过表格和分隔线
            if not l or l.startswith("|") or l.startswith("---"):
                continue
            # 跳过子标题行本身，但继续读后面的正文
            if l.startswith("###"):
                continue
            # 遇到下一级 ## 标题就停
            if l.startswith("##"):
                break
            # 收集足够长的正文行
            if len(l) > 12:
                l = _strip_markdown(l)
                body_parts.append(l)
            if len(body_parts) >= 3:
                break
        body = " ".join(body_parts)
        if heading and body:
            result.append({"heading": heading, "body": body})
    return result


def _build_xhs_body(sections: list[dict]) -> str:
    """拼装小红书正文（无 emoji，纯文字短段落）"""
    priority_keywords = ["简介", "优势", "上岸", "师资", "培养", "课程", "校区",
                         "背景", "评分", "测评", "服务", "人群", "推荐", "核心"]
    selected = []
    for kw in priority_keywords:
        for s in sections:
            if kw in s["heading"] and s not in selected:
                selected.append(s)
                break
    if not selected:
        selected = sections[:5]

    lines = []
    for s in selected:
        lines.append(f"【{s['heading']}】")
        if s["body"]:
            lines.append(s["body"])
        lines.append("")

    highlights = _extract_highlights("\n".join(s["body"] for s in sections))
    if highlights:
        lines.append("核心数据：")
        lines.extend(highlights)
        lines.append("")

    lines.append("了解更多，欢迎私信咨询~")

    body = "\n".join(lines)
    if len(body) > 1000:
        body = body[:997] + "..."
    return body


def _xhs_title(base_title: str, sections: list[dict]) -> str:
    """生成 <=20 字短标题"""
    # 用传入标题，过长则智能截断
    if base_title:
        if len(base_title) <= 20:
            return base_title
        # 在破折号/空格处截断
        return _smart_cut(base_title, 20)

    # 无传入标题，从正文提取
    for s in sections:
        if s["body"]:
            first = s["body"].split("。")[0].strip()
            if 5 <= len(first) <= 20:
                return first
            if len(first) > 20:
                return _smart_cut(first, 20)

    # 最后兜底：取第一个 section 的标题
    if sections:
        heading = sections[0]["heading"]
        return heading[:20] if len(heading) > 20 else heading

    return "本地AI助手"


def _smart_cut(text: str, limit: int) -> str:
    """智能截断：在标点/空格处断，不截半个词"""
    cut = text[:limit]
    for sep in [" — ", " - ", "，", "。", "、", " "]:
        idx = cut.rfind(sep)
        if idx > limit // 2:
            return cut[:idx]
    return cut


# ── 百家号 / 头条号 改写 ──────────────────────────────

def rewrite_for_article(md_text: str, title: str = "") -> dict:
    """
    将 Markdown 转为干净的长文段落，适合百家号、头条号。

    返回: {"title": str, "body": str, "tags": list[str]}
    """
    lines = []
    in_table = False

    for line in md_text.split("\n"):
        stripped = line.strip()

        # 跳过封面大标题
        if stripped.startswith("# ") and not stripped.startswith("## "):
            continue

        # 二级标题
        if stripped.startswith("## "):
            heading = stripped[3:].strip()
            lines.append("")
            lines.append(f"【{heading}】")
            continue

        # 三级标题
        if stripped.startswith("### "):
            sub = stripped[4:].strip()
            lines.append(f"> {sub}")
            continue

        # 表格分隔线
        if stripped.startswith("---") or stripped.startswith("| --"):
            in_table = True
            continue

        # 表格行 → 转成列表项
        if stripped.startswith("|"):
            if not in_table:
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            cells = [c for c in cells if c]
            if cells:
                lines.append("  - " + " / ".join(cells))
            continue

        in_table = False

        # 引用
        if stripped.startswith("> "):
            lines.append("  " + _strip_markdown(stripped[2:]))
            continue

        # 空行
        if not stripped:
            if lines and lines[-1] != "":
                lines.append("")
            continue

        # 普通段落
        clean = _strip_markdown(stripped)
        if len(clean) > 5:
            lines.append(clean)

    body = "\n".join(lines)
    tags = _extract_tags(body)

    return {"title": title or "文章", "body": body, "tags": tags}
