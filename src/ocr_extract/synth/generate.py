"""生成合成样本。

用法: uv run python -m ocr_extract.synth.generate --seed 42 --per-cell 4
"""

import argparse
import json
import random
from pathlib import Path

from PIL import Image

from ocr_extract.schema import ReceiptFields

from . import degrade, templates

TEMPLATES = {"receipt": templates.receipt, "invoice": templates.invoice, "statement": templates.statement}
OUT = Path(__file__).resolve().parents[3] / "data" / "synthetic"


def make_sample(template: str, level: str, index: int, seed: int) -> tuple[Image.Image, dict]:
    sid = f"{template}_{level}_{index:02d}"
    # 每张图用独立的随机数:改动某一张或新增模板,不会让其他样本跟着变
    rng = random.Random(f"{seed}-{sid}")
    font_name = rng.choice(sorted(templates.FONTS))
    font_path = templates.FONTS[font_name]
    r = TEMPLATES[template](rng, font_path)

    # 标签必须能通过 schema,并且本身就是序列化后的标准格式
    assert ReceiptFields.model_validate(r.fields).model_dump(mode="json") == r.fields, sid

    params: dict = {}
    if level == "occlusion":
        # 轮流压收款人 / 金额:随机选时 8 张里只抽中 2 张收款人,样本太少测不出结论。
        # 对账单的 payee_name 固定为 null,只能压金额
        target = ("payee_name" if index % 2 == 0 else "amount") if r.fields["payee_name"] else "amount"
        x0, y0, x1, y1 = r.boxes[target]
        center = ((x0 + x1) // 2 + rng.randint(-20, 20), (y0 + y1) // 2)
        img = degrade.watermark(degrade.stamp(r.image, center, r.stamp_text, font_path), font_path)
        params = {"stamp_on": target}
    else:
        img = degrade.stamp(r.image, r.blank, r.stamp_text, font_path)
        if level != "clean":
            img, params = degrade.DEGRADE[level](img, rng)

    label = {
        "id": sid,
        "template": template,
        "difficulty": level,
        "font": font_name,
        "seed": seed,
        "degrade": params,
        "fields": r.fields,
        "rendered": r.rendered,
    }
    return img, label


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--per-cell", type=int, default=4, help="每个(模板, 难度)组合生成几张")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    (args.out / "images").mkdir(parents=True, exist_ok=True)
    (args.out / "labels").mkdir(parents=True, exist_ok=True)
    count = 0
    for template in TEMPLATES:
        for level in degrade.LEVELS:
            for i in range(args.per_cell):
                img, label = make_sample(template, level, i, args.seed)
                img.save(args.out / "images" / f"{label['id']}.png")
                (args.out / "labels" / f"{label['id']}.json").write_text(
                    json.dumps(label, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                count += 1
    print(f"生成 {count} 张 → {args.out}")


if __name__ == "__main__":
    main()
