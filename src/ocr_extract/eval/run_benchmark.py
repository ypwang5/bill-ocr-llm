"""对多个方案跑同一批样本,按难度/模板分组统计,结果带时间戳存入 results/。

用法:
  uv run python -m ocr_extract.eval.run_benchmark --methods A,B,C --set test --subset10   # 先在 10 张上验证
  uv run python -m ocr_extract.eval.run_benchmark --methods A,B,C --set test              # 全部 72 张
  uv run python -m ocr_extract.eval.run_benchmark --reuse results/<目录> --methods A,B,C,D  # 不调 API,读已有预测重算
"""

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Callable

from ocr_extract.config import ROOT, load_settings
from ocr_extract.eval.compare import SETS, SUBSET10, load_labels, run
from ocr_extract.eval.metrics import FIELDS, compute, grouped
from ocr_extract.extractors.base import ExtractionResult

NAMES = {"A": "A 规则", "B": "B OCR+LLM", "C": "C 多模态", "D": "D 融合路由"}


def make_extractor(method: str, reuse: dict[str, list[dict]]) -> Callable[[Path], ExtractionResult]:
    if method == "A":
        from ocr_extract.extractors.rule_based import extract
        return extract
    if method == "B":
        from ocr_extract.extractors.ocr_llm import OcrLlmExtractor
        return OcrLlmExtractor().extract
    if method == "C":
        from ocr_extract.extractors.vlm_direct import VlmExtractor
        return VlmExtractor().extract
    if method == "D":
        from ocr_extract.extractors.hybrid import HybridExtractor
        return HybridExtractor.from_predictions(reuse).extract if reuse else HybridExtractor().extract
    raise ValueError(method)


def prices(method: str) -> dict:
    if method == "A":
        return {}
    s = load_settings()
    # D 的 token 里混有文本和视觉调用;本项目两者同价,统一按文本价估算(报告中注明)
    if method == "C":
        return {"price_in": s.price_vision_in, "price_out": s.price_vision_out}
    return {"price_in": s.price_text_in, "price_out": s.price_text_out}


def pct(x: float) -> str:
    return f"{x:.0%}"


def report(set_name: str, scope: str, results: dict[str, dict]) -> str:
    methods = list(results)
    out = [f"# Benchmark:{set_name} / {scope}\n"]

    out.append("## 总览\n\n| 方案 | n | 整单全对 | 静默错误率 | 留空率 | 幻觉率 | 格式重试/失败 | P50 | P95 | 单张成本(元) |\n|" + "---|" * 10)
    for m in methods:
        a = results[m]["all"]
        out.append(f"| {NAMES[m]} | {a['n']} | {pct(a['doc_acc'])} | {a['silent_rate']:.1%}({a['silent_count']}) | "
                   f"{a['null_rate']:.1%} | {a['halluc_rate']:.1%} | {pct(a['retry_rate'])}/{pct(a['format_fail_rate'])} | "
                   f"{a['latency_p50']:.1f}s | {a['latency_p95']:.1f}s | {a['cost_per_doc']:.4f} |")

    out.append("\n## 字段准确率\n\n| 方案 | " + " | ".join(FIELDS) + " |\n|" + "---|" * (len(FIELDS) + 1))
    for m in methods:
        out.append(f"| {NAMES[m]} | " + " | ".join(pct(results[m]["all"]["field_acc"][f]) for f in FIELDS) + " |")

    for key, title in (("difficulty", "难度"), ("template", "票据类型")):
        groups = list(results[methods[0]][key])
        out.append(f"\n## 整单全对 × {title}\n\n| 方案 | " + " | ".join(groups) + " |\n|" + "---|" * (len(groups) + 1))
        for m in methods:
            out.append(f"| {NAMES[m]} | " + " | ".join(pct(results[m][key][g]["doc_acc"]) for g in groups) + " |")

    groups = list(results[methods[0]]["difficulty"])
    out.append("\n## 静默错误数 × 难度\n\n| 方案 | " + " | ".join(groups) + " |\n|" + "---|" * (len(groups) + 1))
    for m in methods:
        out.append(f"| {NAMES[m]} | " + " | ".join(str(results[m]["difficulty"][g]["silent_count"]) for g in groups) + " |")
    return "\n".join(out) + "\n"


def load_reuse(folder: Path) -> dict[str, list[dict]]:
    return {p.stem: [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()] for p in folder.glob("[A-D].jsonl")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", default="A,B,C")
    ap.add_argument("--set", choices=SETS, default="test")
    ap.add_argument("--subset10", action="store_true")
    ap.add_argument("--reuse", type=Path, help="读这个目录里已有的 <方案>.jsonl,不重新调用")
    args = ap.parse_args()

    reuse = load_reuse(args.reuse) if args.reuse else {}
    if args.reuse:
        args.set = json.loads((args.reuse / "config.json").read_text(encoding="utf-8"))["set"]
    labels = load_labels(args.set, SUBSET10 if args.subset10 else None)
    ids = {l["id"] for l in labels}
    scope = "SUBSET10" if args.subset10 else "全部"

    rows, results = {}, {}
    for m in args.methods.split(","):
        if m in reuse and m != "D":
            rows[m] = [r for r in reuse[m] if r["id"] in ids]
        else:
            print(f"运行方案 {m} ...", flush=True)
            rows[m] = run(labels, args.set, make_extractor(m, reuse))
        for r in rows[m]:
            r["method"] = m
        p = prices(m)
        results[m] = {"all": compute(rows[m], **p), "difficulty": grouped(rows[m], "difficulty", **p),
                      "template": grouped(rows[m], "template", **p)}

    out = ROOT / "results" / f"{dt.datetime.now():%Y%m%d_%H%M%S}_benchmark_{args.set}{'_subset10' if args.subset10 else ''}"
    out.mkdir(parents=True)
    s = load_settings()
    config = {"set": args.set, "scope": scope, "n": len(labels), "methods": list(rows), "reuse": str(args.reuse or ""),
              "llm": s.public(), "use_doc_unwarping": True}
    (out / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    for m, rs in rows.items():
        (out / f"{m}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rs), encoding="utf-8")
    (out / "metrics.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    text = report(args.set, scope, results)
    (out / "report.md").write_text(text, encoding="utf-8")
    print(text)
    print(f"→ {out}")


if __name__ == "__main__":
    main()
