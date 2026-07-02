"""
PDF → Markdown 转换工具

使用 pymupdf4llm 将 PDF 文件转换为 Markdown 格式。
支持文字型 PDF，如果 PDF 是扫描件（图片型），会先诊断并提示。

用法:
    python pdf_to_markdown.py input.pdf                    # 输出 input.md
    python pdf_to_markdown.py input.pdf -o output.md       # 指定输出路径
    python pdf_to_markdown.py input.pdf --diagnose         # 仅诊断 PDF 类型
"""

import argparse
import sys
from pathlib import Path

import fitz


def diagnose(pdf_path: str | Path) -> dict:
    """诊断 PDF：判断是否文字型、页数、图片数量"""
    doc = fitz.open(str(pdf_path))
    info = {
        "path": str(pdf_path),
        "pages": doc.page_count,
        "file_size_mb": Path(pdf_path).stat().st_size / (1024 * 1024),
        "has_text": False,
        "image_count": 0,
        "text_per_page": [],
    }

    for i in range(doc.page_count):
        page = doc[i]
        text = page.get_text().strip()
        imgs = page.get_images()
        chars = len(text)
        img_count = len(imgs)
        info["text_per_page"].append({"page": i + 1, "chars": chars, "images": img_count})
        info["image_count"] += img_count
        if chars > 50:
            info["has_text"] = True

    info["avg_chars_per_page"] = sum(p["chars"] for p in info["text_per_page"]) / max(doc.page_count, 1)
    doc.close()
    return info


def print_diagnosis(info: dict):
    """打印诊断结果"""
    print(f"文件: {info['path']}")
    print(f"大小: {info['file_size_mb']:.1f} MB")
    print(f"页数: {info['pages']}")
    print(f"图片: {info['image_count']} 张")
    print(f"平均每页文字: {info['avg_chars_per_page']:.0f} 字")
    print()

    if not info["has_text"]:
        print("⚠️  [扫描件/图片型 PDF]  所有页面均无文字，需要 OCR 处理。")
        print("   此工具不支持 OCR。请使用以下方案之一：")
        print("   1. marker-pdf (pip install marker-pdf) — 需要 ~5GB 空间")
        print("   2. 在线 OCR 服务 (如 Adobe Acrobat、SmallPDF)")
    else:
        print("✅ [文字型 PDF]  可以直接转换。")

    # 逐页详情
    for p in info["text_per_page"]:
        flag = "" if p["chars"] > 50 else " ⚠️ 几乎无文字"
        print(f"   第 {p['page']:>3} 页: {p['chars']:>5} 字, {p['images']:>2} 张图片{flag}")


# 项目内容素材目录
CONTENT_DIR = Path(__file__).parent / "content"


def convert(pdf_path: str | Path, output_path: str | Path | None = None) -> Path:
    """将 PDF 转换为 Markdown"""
    pdf_path = Path(pdf_path)
    if output_path is None:
        # 默认输出到 content/ 目录
        CONTENT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = CONTENT_DIR / pdf_path.with_suffix(".md").name
    else:
        output_path = Path(output_path)

    # 诊断
    info = diagnose(pdf_path)
    if not info["has_text"]:
        print_diagnosis(info)
        sys.exit(1)

    # 转换
    import pymupdf4llm
    print(f"正在转换 {pdf_path.name} ({info['pages']} 页)...")
    md_text = pymupdf4llm.to_markdown(str(pdf_path))

    # 写入
    output_path.write_text(md_text, encoding="utf-8")
    size_kb = output_path.stat().st_size / 1024
    print(f"✅ 已生成: {output_path} ({size_kb:.1f} KB)")

    return output_path


def main():
    parser = argparse.ArgumentParser(description="PDF → Markdown 转换工具")
    parser.add_argument("pdf", help="PDF 文件路径")
    parser.add_argument("-o", "--output", help="输出 Markdown 文件路径（默认 content/<pdf名>.md）")
    parser.add_argument("--diagnose", action="store_true", help="仅诊断，不转换")
    args = parser.parse_args()

    if not Path(args.pdf).exists():
        print(f"❌ 文件不存在: {args.pdf}")
        sys.exit(1)

    if args.diagnose:
        info = diagnose(args.pdf)
        print_diagnosis(info)
    else:
        convert(args.pdf, args.output)


if __name__ == "__main__":
    main()
