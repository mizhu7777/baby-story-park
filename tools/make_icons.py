#!/usr/bin/env python3
"""生成 PWA 图标（纯 Pillow 绘制，不依赖任何外部素材）。"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "icons"

CREAM = (255, 246, 236)
CORAL = (255, 138, 91)
CORAL_DARK = (244, 112, 60)
SUN = (255, 201, 77)
MINT = (79, 195, 174)
INK = (74, 55, 40)


def rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def base(size, pad_ratio):
    """pad_ratio 控制安全区：maskable 图标留出更大的边距。"""
    img = Image.new("RGB", (size, size), CREAM)
    d = ImageDraw.Draw(img)

    # 背景：柔和暖色对角渐变块
    step = max(size // 60, 1)
    for i in range(0, size, step):
        t = i / size
        col = (
            int(255 + (255 - 244) * t),
            int(246 + (238 - 246) * t),
            int(236 + (224 - 236) * t),
        )
        d.rectangle([i, 0, i + step, size], fill=col)

    p = int(size * pad_ratio)
    inner = size - 2 * p

    # 书本主体
    book = [p, p + int(inner * 0.12), size - p, size - p - int(inner * 0.06)]
    rounded(d, book, int(inner * 0.1), CORAL)
    rounded(d, [book[0], book[1], book[2], book[1] + int(inner * 0.1)], int(inner * 0.05), CORAL_DARK)

    # 中缝
    mid = (book[0] + book[2]) // 2
    d.rectangle([mid - int(size * 0.008), book[1] + int(inner * 0.08), mid + int(size * 0.008), book[3]],
                fill=(255, 255, 255))

    # 页面上的小星星（故事感）
    cx, cy, r = book[0] + int(inner * 0.24), book[1] + int(inner * 0.52), int(inner * 0.11)
    star = []
    import math

    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.45
        star.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    d.polygon(star, fill=SUN)

    # 右页：一个绿色小圆形 + 一条书脊线
    d.ellipse(
        [book[2] - int(inner * 0.36), book[1] + int(inner * 0.38),
         book[2] - int(inner * 0.16), book[1] + int(inner * 0.58)],
        fill=MINT,
    )
    for k in range(3):
        y = book[1] + int(inner * (0.66 + k * 0.08))
        d.rounded_rectangle(
            [mid + int(inner * 0.08), y, book[2] - int(inner * 0.1), y + int(inner * 0.035)],
            radius=int(inner * 0.02),
            fill=(255, 255, 255, 255),
        )
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for size, name, pad in [
        (192, "icon-192.png", 0.13),
        (512, "icon-512.png", 0.13),
        (512, "icon-maskable-512.png", 0.24),
        (180, "apple-touch-icon.png", 0.10),
    ]:
        img = base(size, pad)
        img.save(OUT / name, "PNG", optimize=True)
        print(f"{name}: {size}x{size}  {(OUT / name).stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
