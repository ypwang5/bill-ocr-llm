"""方案 A 跑一批样本,和标签逐字段对比。完整评估框架在 2.2,这里只做简单对比。

用法:
  uv run python scripts/run_rule_based.py --set dev                # 开发集,用来写规则、选 UVDoc
  uv run python scripts/run_rule_based.py --set dev --uvdoc off
  uv run python scripts/run_rule_based.py --set test               # 测试集,只在最后跑
"""

import argparse
import datetime as dt

from ocr_extract.config import ROOT
from ocr_extract.eval.compare import SETS, SUBSET10, errors_table, load_labels, run, save, summarize
from ocr_extract.extractors.rule_based import extract


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=SETS, required=True)
    ap.add_argument("--uvdoc", choices=["on", "off"], default="on")
    args = ap.parse_args()
    unwarp = args.uvdoc == "on"

    rows = run(load_labels(args.set), args.set, lambda p: extract(p, use_doc_unwarping=unwarp))

    report = [summarize(rows, "全部")]
    if args.set == "test":
        report.append(summarize([r for r in rows if r["id"] in SUBSET10], "SUBSET10(与方案 B 对比)"))
    report.append(errors_table(rows))

    # 不覆盖旧结果:目录带时间戳
    out = ROOT / "results" / f"{dt.datetime.now():%Y%m%d_%H%M%S}_rule_based_{args.set}_uvdoc-{args.uvdoc}"
    save(out, {"set": args.set, "use_doc_unwarping": unwarp, "n": len(rows)}, rows, report)
    print("\n\n".join(report))
    print(f"\n→ {out}")


if __name__ == "__main__":
    main()
