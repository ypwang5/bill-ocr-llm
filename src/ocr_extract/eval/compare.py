"""各方案共用的简单打分和报表。完整评估框架在 2.2,这里先保证 A、B 用同一套打分代码。"""

import collections
import json
import statistics
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from ocr_extract.config import ROOT
from ocr_extract.extractors.base import FIELDS, ExtractionResult

SETS = {"dev": ROOT / "data" / "synthetic_dev", "tune": ROOT / "data" / "synthetic_tune", "test": ROOT / "data" / "synthetic"}

# 与方案 B 对比用的 10 张,在看到任何结果之前就定好(见 1.5 方案)
SUBSET10 = [
    "receipt_clean_00", "invoice_blur_00", "receipt_rotate_00", "invoice_lowres_00",
    "receipt_perspective_00", "invoice_occlusion_00", "receipt_occlusion_01",
    "statement_clean_00", "statement_rotate_00", "statement_occlusion_00",
]


def load_labels(set_name: str, ids: list[str] | None = None) -> list[dict]:
    labels = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((SETS[set_name] / "labels").glob("*.json"))]
    return [l for l in labels if ids is None or l["id"] in ids]


def run(labels: list[dict], set_name: str, extract: Callable[[Path], ExtractionResult]) -> list[dict]:
    rows = []
    for label in labels:
        r = extract(SETS[set_name] / "images" / f"{label['id']}.png")
        correct = {f: r.fields[f] == label["fields"][f] for f in FIELDS}
        rows.append({"id": label["id"], "template": label["template"], "difficulty": label["difficulty"],
                     "correct": correct, "pred": r.fields, "gold": label["fields"], **asdict(r)})
    return rows


def summarize(rows: list[dict], title: str) -> str:
    groups = collections.defaultdict(list)
    for r in rows:
        groups[r["difficulty"]].append(r)
    groups["合计"] = rows
    head = (f"### {title}(n={len(rows)})\n\n| 难度 | n | " + " | ".join(FIELDS)
            + " | 整单全对 | 静默错 | 幻觉 |\n|" + "---|" * (len(FIELDS) + 5))
    lines = [head]
    for name, rs in groups.items():
        acc = [sum(r["correct"][f] for r in rs) / len(rs) for f in FIELDS]
        whole = sum(all(r["correct"].values()) for r in rs) / len(rs)
        lines.append(f"| {name} | {len(rs)} | " + " | ".join(f"{a:.0%}" for a in acc)
                     + f" | {whole:.0%} | {silent_errors(rs)} | {hallucinations(rs)} |")
    return "\n".join(lines)


def silent_errors(rows: list[dict]) -> int:
    """输出了值但值是错的:下游发现不了,比 null 危险。"""
    return sum(1 for r in rows for f in FIELDS if r["pred"][f] is not None and r["pred"][f] != r["gold"][f])


def hallucinations(rows: list[dict]) -> int:
    """标签为 null(单据上没有),预测却有值。"""
    return sum(1 for r in rows for f in FIELDS if r["gold"][f] is None and r["pred"][f] is not None)


def perf_table(rows: list[dict], price_in: float = 0.0, price_out: float = 0.0) -> str:
    def p(values: list[float], q: float) -> float:
        return statistics.quantiles(values, n=100, method="inclusive")[q - 1] if len(values) > 1 else values[0]

    extra = [r["latency_s"] - r["ocr_latency_s"] for r in rows]  # 抽取本身(规则或 LLM)的耗时
    t_in, t_out = sum(r["tokens_in"] for r in rows), sum(r["tokens_out"] for r in rows)
    cost = (t_in * price_in + t_out * price_out) / 1_000_000
    return "\n".join([
        "### 耗时与成本\n\n| 指标 | 值 |\n|---|---|",
        f"| 抽取耗时 P50 / P95(不含 OCR) | {p(extra, 50):.2f}s / {p(extra, 95):.2f}s |",
        f"| 总耗时 P50 / P95(含首次 OCR) | {p([r['latency_s'] for r in rows], 50):.1f}s / {p([r['latency_s'] for r in rows], 95):.1f}s |",
        f"| token 输入 / 输出(合计) | {t_in} / {t_out} |",
        f"| 单张成本 | {cost / len(rows):.5f}(合计 {cost:.4f}) |",
        f"| 格式重试 / 重试后仍失败 | {sum(r['retries'] > 0 for r in rows)} / {sum(r['format_failed'] for r in rows)} 张 |",
    ])


def errors_table(rows: list[dict]) -> str:
    lines = ["### 错误明细\n\n| id | 字段 | 预测 | 标准答案 | 校验错误 |\n|---|---|---|---|---|"]
    for r in rows:
        for f in FIELDS:
            if not r["correct"][f]:
                lines.append(f"| {r['id']} | {f} | {r['pred'][f]} | {r['gold'][f]} | {r['field_errors'].get(f, '')} |")
    return "\n".join(lines)


def save(out: Path, config: dict, rows: list[dict], report: list[str]) -> None:
    out.mkdir(parents=True)
    (out / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(out / "predictions.jsonl", "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out / "summary.md").write_text("\n\n".join(report), encoding="utf-8")
