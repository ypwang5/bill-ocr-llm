"""方案 A 跑一批样本,和标签逐字段对比。完整评估框架在 2.2,这里只做简单对比。

用法:
  uv run python scripts/run_rule_based.py --set dev                # 开发集,用来写规则、选 UVDoc
  uv run python scripts/run_rule_based.py --set dev --uvdoc off
  uv run python scripts/run_rule_based.py --set test               # 测试集,只在最后跑
"""

import argparse
import collections
import datetime as dt
import json
from dataclasses import asdict
from pathlib import Path

from ocr_extract.extractors.base import FIELDS
from ocr_extract.extractors.rule_based import extract

ROOT = Path(__file__).resolve().parent.parent
SETS = {"dev": ROOT / "data" / "synthetic_dev", "test": ROOT / "data" / "synthetic"}

# 与方案 B 对比用的 10 张,在看到任何结果之前就定好(见 1.5 方案)
SUBSET10 = [
    "receipt_clean_00", "invoice_blur_00", "receipt_rotate_00", "invoice_lowres_00",
    "receipt_perspective_00", "invoice_occlusion_00", "receipt_occlusion_01",
    "statement_clean_00", "statement_rotate_00", "statement_occlusion_00",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=SETS, required=True)
    ap.add_argument("--uvdoc", choices=["on", "off"], default="on")
    args = ap.parse_args()
    unwarp = args.uvdoc == "on"

    labels = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((SETS[args.set] / "labels").glob("*.json"))]
    rows = []
    for label in labels:
        r = extract(SETS[args.set] / "images" / f"{label['id']}.png", use_doc_unwarping=unwarp)
        correct = {f: r.fields[f] == label["fields"][f] for f in FIELDS}
        rows.append({"id": label["id"], "template": label["template"], "difficulty": label["difficulty"],
                     "correct": correct, "pred": r.fields, "gold": label["fields"], **asdict(r)})

    # 不覆盖旧结果:目录带时间戳
    out = ROOT / "results" / f"{dt.datetime.now():%Y%m%d_%H%M%S}_rule_based_{args.set}_uvdoc-{args.uvdoc}"
    out.mkdir(parents=True)
    (out / "config.json").write_text(json.dumps({"set": args.set, "use_doc_unwarping": unwarp, "n": len(rows)}, indent=2), encoding="utf-8")
    with open(out / "predictions.jsonl", "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    report = [summarize(rows, "全部")]
    if args.set == "test":
        report.append(summarize([r for r in rows if r["id"] in SUBSET10], "SUBSET10(与方案 B 对比)"))
    report.append(errors_table(rows))
    (out / "summary.md").write_text("\n\n".join(report), encoding="utf-8")
    print("\n\n".join(report))
    print(f"\n→ {out}")


def summarize(rows: list[dict], title: str) -> str:
    groups = collections.defaultdict(list)
    for r in rows:
        groups[r["difficulty"]].append(r)
    groups["合计"] = rows
    head = f"### {title}(n={len(rows)})\n\n| 难度 | n | " + " | ".join(FIELDS) + " | 整单全对 | 幻觉 |\n|" + "---|" * (len(FIELDS) + 4)
    lines = [head]
    for name, rs in groups.items():
        acc = [sum(r["correct"][f] for r in rs) / len(rs) for f in FIELDS]
        whole = sum(all(r["correct"].values()) for r in rs) / len(rs)
        # 幻觉:标签为 null,预测却有值
        halluc = sum(1 for r in rs for f in FIELDS if r["gold"][f] is None and r["pred"][f] is not None)
        lines.append(f"| {name} | {len(rs)} | " + " | ".join(f"{a:.0%}" for a in acc) + f" | {whole:.0%} | {halluc} |")
    return "\n".join(lines)


def errors_table(rows: list[dict]) -> str:
    lines = ["### 错误明细\n\n| id | 字段 | 预测 | 标准答案 | 校验错误 |\n|---|---|---|---|---|"]
    for r in rows:
        for f in FIELDS:
            if not r["correct"][f]:
                lines.append(f"| {r['id']} | {f} | {r['pred'][f]} | {r['gold'][f]} | {r['field_errors'].get(f, '')} |")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
