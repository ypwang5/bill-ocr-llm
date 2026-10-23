"""6 档难度退化。每档只施加一种,出错时才能归因到具体原因(控制变量)。

每个函数返回 (图片, 参数),参数写进标签,方便之后分析"旋转角度越大是否越容易错"。
"""

import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .templates import font

LEVELS = ("clean", "blur", "rotate", "lowres", "perspective", "occlusion")

# 半透明:人眼仍能透过印章读出下面的字,所以标签保持真实值
STAMP_RED = (215, 30, 30, 150)


def stamp(img: Image.Image, center: tuple[int, int], lines: tuple[str, str], font_path: str, radius: int = 75) -> Image.Image:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = center
    d.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=STAMP_RED, width=5)
    d.text((cx, cy - 30), "★", font=font(font_path, 30), fill=STAMP_RED, anchor="mm")
    d.text((cx, cy + 8), lines[0], font=font(font_path, 20), fill=STAMP_RED, anchor="mm")
    d.text((cx, cy + 36), lines[1], font=font(font_path, 16), fill=STAMP_RED, anchor="mm")
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def watermark(img: Image.Image, font_path: str) -> Image.Image:
    w, h = img.size
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = font(font_path, 40)
    for row, y in enumerate(range(-h, 2 * h, 160)):
        for x in range(-w, 2 * w, 380):
            d.text((x + row % 2 * 190, y), "合成样本 SAMPLE", font=f, fill=(110, 110, 110, 70))
    layer = layer.rotate(25, resample=Image.BICUBIC)
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def blur(img: Image.Image, rng: random.Random) -> tuple[Image.Image, dict]:
    radius = round(rng.uniform(1.5, 2.5), 2)
    return img.filter(ImageFilter.GaussianBlur(radius)), {"blur_radius": radius}


def rotate(img: Image.Image, rng: random.Random) -> tuple[Image.Image, dict]:
    angle = round(rng.choice([-1, 1]) * rng.uniform(5, 15), 2)
    return img.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor="white"), {"angle": angle}


def lowres(img: Image.Image, rng: random.Random) -> tuple[Image.Image, dict]:
    # 缩小再放大回原尺寸:像素信息丢了,但图片尺寸不变,检测模型的输入尺度不受影响
    scale = round(rng.uniform(0.35, 0.5), 2)
    w, h = img.size
    small = img.resize((int(w * scale), int(h * scale)), Image.BILINEAR)
    return small.resize((w, h), Image.BILINEAR), {"scale": scale}


def _perspective_coeffs(out_pts: list[tuple[float, float]], in_pts: list[tuple[float, float]]) -> list[float]:
    """PIL 的 PERSPECTIVE 要的是"输出坐标 → 输入坐标"的 8 个系数,解 8 元线性方程组得到。"""
    a, b = [], []
    for (x, y), (u, v) in zip(out_pts, in_pts):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b += [u, v]
    return np.linalg.solve(np.array(a, float), np.array(b, float)).tolist()


def perspective(img: Image.Image, rng: random.Random) -> tuple[Image.Image, dict]:
    """模拟手机俯拍:票据放在灰色桌面上,四个角各自向内随机偏移。"""
    w, h = img.size
    pad = int(0.08 * max(w, h))
    gray = rng.randint(140, 190)
    canvas = Image.new("RGB", (w + 2 * pad, h + 2 * pad), (gray, gray, gray))
    canvas.paste(img, (pad, pad))
    src = [(pad, pad), (pad + w, pad), (pad + w, pad + h), (pad, pad + h)]
    ratio = round(rng.uniform(0.05, 0.12), 3)
    inward = [(1, 1), (-1, 1), (-1, -1), (1, -1)]
    dst = [(x + sx * rng.uniform(0, ratio) * w, y + sy * rng.uniform(0, ratio) * h) for (x, y), (sx, sy) in zip(src, inward)]
    out = canvas.transform(canvas.size, Image.PERSPECTIVE, _perspective_coeffs(dst, src), Image.BICUBIC, fillcolor=(gray, gray, gray))
    return out, {"max_corner_shift": ratio}


DEGRADE = {"blur": blur, "rotate": rotate, "lowres": lowres, "perspective": perspective}
