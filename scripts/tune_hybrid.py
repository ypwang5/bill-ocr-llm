"""在调参集(dev 18 + tune 36)上用回放选方案 D 的路由配置。不调用任何 API。

选择规则(看结果之前定好,见 D24):
  1. D 的静默错误数不能多于 B(D 不能比 B 更危险)
  2. 满足 1 的配置里,整单全对率最高
  3. 再并列时,回退比例最低(最省钱)

用法:uv run python scripts/tune_hybrid.py results/<dev 的 benchmark 目录> results/<tune 的 benchmark 目录>
"""

import itertools
import sys
from pathlib import Path

from ocr_extract.config import load_settings
from ocr_extract.eval.compare import load_labels, run
from ocr_extract.eval.metrics import compute
from ocr_extract.eval.run_benchmark import load_reuse
from ocr_extract.extractors.hybrid import HybridExtractor, RouteConfig

GRID = {
    "min_mean_score": [0.0, 0.90, 0.93, 0.95, 0.97, 0.98],
    "check_daxie": [False, True],
    "merge": ["fill", "agree", "replace"],
    "check_serial": [False, True],
}


def main() -> None:
    s = load_settings()
    folders = [Path(p) for p in sys.argv[1:]]
    sets = [(f, __import__("json").loads((f / "config.json").read_text(encoding="utf-8"))["set"]) for f in folders]
    preds = {f: load_reuse(f) for f, _ in sets}

    def rows_for(cfg: RouteConfig | None, method: str = "D") -> list[dict]:
        out = []
        for f, set_name in sets:
            if cfg is None:
                out += preds[f][method]
            else:
                out += run(load_labels(set_name), set_name, HybridExtractor.from_predictions(preds[f], cfg).extract)
        return out

    base = {m: compute(rows_for(None, m)) for m in ("B", "C")}
    print(f"调参集 n={base['B']['n']}:B 整单 {base['B']['doc_acc']:.1%} 静默 {base['B']['silent_count']};"
          f"C 整单 {base['C']['doc_acc']:.1%} 静默 {base['C']['silent_count']}\n")
    print("| 平均置信度阈值 | 大写校验 | 合并 | 编号格式 | 整单全对 | 静默错 | 留空率 | 回退比例 | 单张成本 |\n|---|---|---|---|---|---|---|---|---|")
    results = []
    for values in itertools.product(*GRID.values()):
        cfg = RouteConfig(**dict(zip(GRID, values)))
        rows = rows_for(cfg)
        m = compute(rows, price_in=s.price_text_in, price_out=s.price_text_out)  # 本项目文本、视觉同价
        fb = sum(r["fallback"] for r in rows) / len(rows)
        results.append((cfg, m, fb))
        print(f"| {cfg.min_mean_score or '不用'} | {'是' if cfg.check_daxie else '否'} | {cfg.merge} | {'是' if cfg.check_serial else '否'} | {m['doc_acc']:.1%} | "
              f"{m['silent_count']} | {m['null_rate']:.1%} | {fb:.0%} | {m['cost_per_doc']:.4f} |")

    ok = [x for x in results if x[1]["silent_count"] <= base["B"]["silent_count"]]
    best = max(ok, key=lambda x: (round(x[1]["doc_acc"], 6), -x[2]))
    print(f"\n选中:{best[0]}  整单 {best[1]['doc_acc']:.1%}  静默 {best[1]['silent_count']}  回退 {best[2]:.0%}")


if __name__ == "__main__":
    main()
