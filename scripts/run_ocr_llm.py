"""方案 B(或 --method vlm 跑方案 C)跑一批样本;同时用同一份 OCR 缓存跑方案 A,并排对比。

用法:
  uv run python scripts/run_ocr_llm.py --set dev                   # 开发集 18 张,只在这里调提示词
  uv run python scripts/run_ocr_llm.py --set test --subset10       # 冻结提示词后跑一次,与 A 对比
  uv run python scripts/run_ocr_llm.py --method vlm --set dev      # 方案 C
"""

import argparse
import datetime as dt

from ocr_extract.config import ROOT
from ocr_extract.eval.compare import SETS, SUBSET10, errors_table, load_labels, perf_table, run, save, summarize
from ocr_extract.extractors import rule_based
from ocr_extract.extractors.ocr_llm import OcrLlmExtractor
from ocr_extract.extractors.vlm_direct import VlmExtractor


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=SETS, required=True)
    ap.add_argument("--subset10", action="store_true", help="只跑测试集里事先定好的 10 张")
    ap.add_argument("--prompt", default="v1")
    ap.add_argument("--method", choices=["ocr_llm", "vlm"], default="ocr_llm")
    args = ap.parse_args()
    if args.subset10 and args.set != "test":
        ap.error("--subset10 只用于测试集")

    labels = load_labels(args.set, SUBSET10 if args.subset10 else None)
    b = (OcrLlmExtractor if args.method == "ocr_llm" else VlmExtractor)(prompt_version=args.prompt)
    s = b.client.settings
    model = s.model_text if args.method == "ocr_llm" else s.model_vision
    print(f"{args.method} 模型 {model},提示词 {args.prompt} sha256={b.prompt_sha256[:12]},共 {len(labels)} 张")

    rows_b = run(labels, args.set, b.extract)
    rows_a = run(labels, args.set, rule_based.extract)  # 读缓存,几秒内完成

    scope = "SUBSET10" if args.subset10 else "全部"
    report = [
        summarize(rows_b, f"{'方案 B' if args.method == 'ocr_llm' else '方案 C'} {scope}"),
        summarize(rows_a, f"方案 A {scope}(同一批,作对照)"),
        perf_table(rows_b, *((s.price_text_in, s.price_text_out) if args.method == "ocr_llm" else (s.price_vision_in, s.price_vision_out))),
        errors_table(rows_b),
    ]
    tag = f"{args.set}{'_subset10' if args.subset10 else ''}"
    out = ROOT / "results" / f"{dt.datetime.now():%Y%m%d_%H%M%S}_{args.method}-{args.prompt}_{tag}"
    config = {"set": args.set, "ids": [l["id"] for l in labels], "use_doc_unwarping": True,
              "method": args.method, "prompt_version": args.prompt, "prompt_sha256": b.prompt_sha256, "llm": s.public()}
    save(out, config, rows_b, report)
    print("\n\n".join(report))
    print(f"\n→ {out}")


if __name__ == "__main__":
    main()
