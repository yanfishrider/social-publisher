"""
压缩图片 — 确保图片文件大小在平台限制范围内
"""
from PIL import Image
import os


def compress_image(image_path: str, max_size_mb: float = 5, quality: int = 85) -> str | None:
    """
    压缩图片，输出 PNG 格式

    Args:
        image_path: 原始图片路径
        max_size_mb: 最大文件大小（MB）
        quality: 压缩质量 1-100

    Returns:
        压缩后的 PNG 图片路径，失败返回 None
    """
    try:
        if not os.path.exists(image_path):
            print(f"❌ 图片文件不存在: {image_path}")
            return None

        original_size = os.path.getsize(image_path)
        original_mb = original_size / (1024 * 1024)
        print(f"📊 原始大小: {original_mb:.2f}MB → 限制: {max_size_mb}MB")

        with Image.open(image_path) as img:
            width, height = img.size

            if original_mb <= max_size_mb:
                print("✅ 图片大小已在限制内，无需压缩")
                return image_path

            # 转换 RGBA 以支持 PNG 透明
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            # 逐步缩小直到满足大小限制
            file_dir = os.path.dirname(image_path) or "."
            file_name = os.path.basename(image_path)
            name, _ = os.path.splitext(file_name)
            compressed_path = os.path.join(file_dir, f"{name}_compressed.png")

            scale = 1.0
            for attempt in range(20):
                new_w = int(width * scale)
                new_h = int(height * scale)
                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS) if scale < 1.0 else img
                compress_level = min(9, int((100 - quality) / 10))
                resized.save(compressed_path, "PNG", optimize=True, compress_level=compress_level)

                new_mb = os.path.getsize(compressed_path) / (1024 * 1024)
                if new_mb <= max_size_mb:
                    print(f"✅ 压缩成功: {original_mb:.2f}MB → {new_mb:.2f}MB ({new_w}x{new_h})")
                    return compressed_path

                scale -= 0.05
                if scale < 0.2:
                    break

            print(f"⚠️ 无法压缩到 {max_size_mb}MB 以下，返回最小版本")
            return compressed_path

    except ImportError:
        print("❌ 缺少 Pillow 库: uv add Pillow")
        return None
    except Exception as e:
        print(f"❌ 图片压缩失败: {e}")
        return None
