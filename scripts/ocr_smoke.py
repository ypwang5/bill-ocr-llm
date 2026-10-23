"""PaddleOCR 冒烟测试:只验证"能跑起来",不验证准确率。

用法: uv run python scripts/ocr_smoke.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from paddleocr import PaddleOCR

IMG_PATH = Path(__file__).resolve().parent.parent / "data" / "smoke" / "smoke.png"
# 虚构内容,不含任何真实信息
LINES = ["转账回单", "付款人:星河科技有限公司", "收款人:云帆贸易有限公司", "金额:¥12,500.00", "日期:2026-03-15"]


def make_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (640, 320), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", 28)
    for i, line in enumerate(LINES):
        draw.text((40, 30 + i * 55), line, fill="black", font=font)
    img.save(path)


def main() -> None:
    make_image(IMG_PATH)
    # 3.x 默认:PP-OCRv6_medium 检测+识别,预处理全开。
    # 关 oneDNN:paddle 3.3.1 在 Windows CPU 上走 oneDNN 时,检测模型报
    # NotImplementedError(ConvertPirAttribute2RuntimeAttribute),见 docs/decisions.md D7
    ocr = PaddleOCR(enable_mkldnn=False)
    result = ocr.predict(str(IMG_PATH))[0]

    for text, score, poly in zip(result["rec_texts"], result["rec_scores"], result["rec_polys"]):
        corners = [tuple(int(v) for v in pt) for pt in poly]
        print(f"{score:.3f}  {text:<24}  {corners}")


if __name__ == "__main__":
    main()
