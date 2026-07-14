"""
内容改写模块 — 基于 MD 语义结构的智能截取

解析 Markdown 层级（# > ## > ### > 列表/段落），按优先级截取至平台字数限制。
"""
import re
from dataclasses import dataclass, field


# ── 数据结构 ──────────────────────────────────────────

@dataclass
class Block:
    """Markdown 块"""
    type: str          # "h1" | "h2" | "h3" | "list" | "paragraph" | "quote"
    content: str       # 纯文本内容
    items: list[str] = field(default_factory=list)  # 列表项


@dataclass
class Section:
    """由 ## 分隔的章节"""
    heading: str       # ## 标题
    blocks: list[Block] = field(default_factory=list)

    @property
    def total_chars(self) -> int:
        return sum(len(b.content) + sum(len(i) for i in b.items) for b in self.blocks)


@dataclass
class Document:
    """解析后的 Markdown 文档"""
    title: str = ""
    sections: list[Section] = field(default_factory=list)


# ── 解析器 ────────────────────────────────────────────

def parse_markdown(text: str) -> Document:
    """解析 Markdown 为结构化 Document"""
    doc = Document()
    current_section = None
    current_block = None
    current_h3 = None
    list_items = []

    def flush_list():
        nonlocal list_items
        if list_items and current_section:
            current_section.blocks.append(Block("list", "", list_items.copy()))
        list_items.clear()

    def flush_paragraph():
        nonlocal current_block
        if current_block is not None and current_section is not None:
            current_section.blocks.append(current_block)
        current_block = None

    for line in text.split("\n"):
        stripped = line.strip()

        # 跳过表格、水平线
        if stripped.startswith("|") or re.match(r"^[-*_]{3,}$", stripped):
            flush_list()
            flush_paragraph()
            continue

        # # 一级标题 → 第一个作文档标题，后续降级为 ##
        m = re.match(r"^# (.+)", stripped)
        if m and not stripped.startswith("##"):
            flush_list()
            flush_paragraph()
            heading = _clean(m.group(1))
            if not doc.title:
                doc.title = heading
            else:
                current_section = Section(heading=heading)
                doc.sections.append(current_section)
            continue

        # ## 二级标题 → 新章节
        m = re.match(r"^## (.+)", stripped)
        if m:
            flush_list()
            flush_paragraph()
            current_section = Section(heading=_clean(m.group(1)))
            doc.sections.append(current_section)
            continue

        # ### 三级标题 → 子标题块
        m = re.match(r"^###\s*(.+)", stripped)
        if m:
            flush_list()
            flush_paragraph()
            if current_section is None:
                current_section = Section(heading="")
                doc.sections.append(current_section)
            current_section.blocks.append(Block("h3", _clean(m.group(1))))
            continue

        # 无序列表
        m = re.match(r"^[-*+]\s+(.+)", stripped)
        if m:
            flush_paragraph()
            list_items.append("  • " + _clean(m.group(1)))
            continue

        # 有序列表
        m = re.match(r"^\d+[.)]\s+(.+)", stripped)
        if m:
            flush_paragraph()
            list_items.append(f"  {m.group(0).split('.')[0]}. " + _clean(m.group(1)))
            continue

        # 引用
        if stripped.startswith("> "):
            flush_list()
            flush_paragraph()
            if current_section is None:
                current_section = Section(heading="")
                doc.sections.append(current_section)
            current_section.blocks.append(Block("quote", "│ " + _clean(stripped[2:])))
            continue

        # 空行 → 结束当前段落
        if not stripped:
            flush_list()
            flush_paragraph()
            continue

        # 普通段落
        clean = _clean(stripped)
        if len(clean) > 3:
            if current_block is None:
                current_block = Block("paragraph", clean)
            else:
                current_block.content += "\n" + clean

    flush_list()
    flush_paragraph()
    return doc


# ── 截取引擎 ──────────────────────────────────────────

def extract_for_limit(doc: Document, limit: int, footer: str = "") -> str:
    """
    按语义优先级截取到 limit 字。

    优先级：标题 > ## 骨架 > ### 子标题 > 列表 > 段落首段 > 段落续段
    """
    lines = []

    # 1. 文档标题
    if doc.title:
        lines.append(doc.title)
        lines.append("─" * min(len(doc.title), 30))
        lines.append("")

    used = sum(len(l) + 1 for l in lines)

    # 2. 每个章节：先保留骨架，再按优先级填充
    section_summaries = []
    for sec in doc.sections:
        if not sec.heading and not sec.blocks:
            continue
        if not sec.heading:
            # 无标题章节的内容作为正文开头
            for blk in sec.blocks:
                if blk.type == "quote":
                    lines.append(blk.content)
                elif blk.type == "paragraph":
                    lines.append(blk.content)
            if lines:
                lines.append("")
            continue

        section_lines = [f"▎{sec.heading}", ""]
        more_lines = []   # 低优先级内容

        for blk in sec.blocks:
            if blk.type == "h3":
                # 子标题 → 高优先级
                section_lines.append(f"  ▸ {blk.content}")
            elif blk.type == "list":
                # 列表 → 高优先级
                for item in blk.items:
                    section_lines.append(item)
            elif blk.type == "quote":
                section_lines.append(blk.content)
            elif blk.type == "paragraph":
                # 段落 → 首段高优先级，续段低优先级
                paras = blk.content.split("\n")
                if paras:
                    section_lines.append(paras[0])
                    for p in paras[1:]:
                        more_lines.append(p)

        section_lines.append("")
        section_summaries.append((section_lines, more_lines))

    # 3. 第一轮：填入所有章节骨架
    truncated = False
    for sec_lines, _ in section_summaries:
        sec_text = "\n".join(sec_lines)
        if used + len(sec_text) > limit - len(footer) - 20:
            lines.append("...")
            truncated = True
            break
        lines.extend(sec_lines)
        used += len(sec_text)

    # 4. 第二轮：填入低优先级段落（未截断时）
    if not truncated:
        for _, more in section_summaries:
            for p in more:
                p_line = p
                if used + len(p_line) + 2 > limit - len(footer) - 20:
                    truncated = True
                    break
                lines.append(p_line)
                used += len(p_line) + 1
            if truncated:
                break

    # 5. 追加尾部
    while lines and not lines[-1]:
        lines.pop()
    if footer:
        lines.append(footer)

    body = "\n".join(lines)
    if len(body) > limit:
        body = body[:limit - 3] + "..."

    return body


# ── 工具函数 ──────────────────────────────────────────

def _clean(text: str) -> str:
    """清除 Markdown 行内语法"""
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", "[图片]", text)
    return text


def _extract_tags(text: str) -> list[str]:
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


# ── 对外接口 ──────────────────────────────────────────

def rewrite_for_xhs(md_text: str, base_title: str = "") -> dict:
    """小红书改写：解析 MD 结构 → 按 1000 字智能截取"""
    doc = parse_markdown(md_text)
    # 标题：用传入的或从文档提取
    title = base_title or doc.title
    if len(title) > 20:
        title = _smart_cut(title, 20)
    body = extract_for_limit(doc, limit=1000, footer="了解更多，欢迎私信咨询~")
    tags = _extract_tags(md_text)
    return {"title": title, "body": body, "tags": tags}


def rewrite_for_article(md_text: str, title: str = "") -> dict:
    """百家号/头条号：全文格式化"""
    body = _format_for_platform_legacy(md_text)
    tags = _extract_tags(body)
    return {"title": title or "文章", "body": body, "tags": tags}


def _format_for_platform_legacy(text: str) -> str:
    """Markdown → 结构化纯文本（mdtotext 风格）"""
    lines_out = []
    prev_empty = True

    for line in text.split("\n"):
        stripped = line.strip()

        if re.match(r"^[-*_]{3,}$", stripped):
            lines_out.append("─" * 40)
            lines_out.append("")
            prev_empty = True
            continue

        if stripped.startswith("|"):
            continue

        m = re.match(r"^# (.+)", stripped)
        if m and not stripped.startswith("##"):
            if not prev_empty:
                lines_out.append("")
            lines_out.append(m.group(1))
            lines_out.append("─" * min(len(m.group(1)), 30))
            lines_out.append("")
            prev_empty = True
            continue

        m = re.match(r"^## (.+)", stripped)
        if m:
            if not prev_empty:
                lines_out.append("")
            lines_out.append("▎" + m.group(1))
            lines_out.append("")
            prev_empty = True
            continue

        m = re.match(r"^###\s*(.+)", stripped)
        if m:
            if not prev_empty:
                lines_out.append("")
            lines_out.append("  ▸ " + m.group(1))
            prev_empty = False
            continue

        if stripped.startswith("> "):
            lines_out.append("│ " + _clean(stripped[2:]))
            prev_empty = False
            continue

        m = re.match(r"^[-*+]\s+(.+)", stripped)
        if m:
            lines_out.append("  • " + _clean(m.group(1)))
            prev_empty = False
            continue

        m = re.match(r"^(\d+)[.)]\s+(.+)", stripped)
        if m:
            lines_out.append(f"  {m.group(1)}. " + _clean(m.group(2)))
            prev_empty = False
            continue

        if not stripped:
            if not prev_empty:
                lines_out.append("")
            prev_empty = True
            continue

        cleaned = _clean(stripped)
        if len(cleaned) > 3:
            lines_out.append(cleaned)
            prev_empty = False

    while lines_out and not lines_out[-1]:
        lines_out.pop()

    return "\n".join(lines_out)


def _smart_cut(text: str, limit: int) -> str:
    cut = text[:limit]
    for sep in [" — ", " - ", "，", "。", "、", " "]:
        idx = cut.rfind(sep)
        if idx > limit // 2:
            return cut[:idx]
    return cut
