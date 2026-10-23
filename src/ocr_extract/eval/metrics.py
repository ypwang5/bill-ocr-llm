"""评估指标。输入是 compare.run 产出的行(每张单据一行),全是纯函数,方便测试。

指标口径(CLAUDE.md 第 8 节 + 1.5/1.6 补充的三项):
- 字段准确率:归一化后完全匹配。null == null 也算对(对账单 payee 本来就该是 null)
- 整单全对率:5 个字段全对
- 格式失败率:LLM 重试一次后仍未通过 pydantic 校验的单据占比;格式重试率:至少重试过一次的占比
- 静默错误率:输出了值但值是错的字段 / 全部字段。下游发现不了,最危险
- 留空率:答案有值、预测为 null 的字段 / 全部字段。能被发现,可转人工或回退
- 幻觉率:答案为 null、预测有值的字段 / 答案为 null 的字段
- 耗时 P50/P95:单张总耗时(含首次 OCR);成本:按 token 和单价估算的单张平均
"""

import collections
import statistics

from ocr_extract.extractors.base import FIELDS


def is_silent(pred: str | None, gold: str | None) -> bool:
    return pred is not None and pred != gold


def percentile(values: list[float], q: int) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[q - 1]


def compute(rows: list[dict], price_in: float = 0.0, price_out: float = 0.0) -> dict:
    n = len(rows)
    if n == 0:
        return {"n": 0}
    n_fields = n * len(FIELDS)
    pairs = [(r["pred"][f], r["gold"][f]) for r in rows for f in FIELDS]
    gold_null = sum(1 for _, g in pairs if g is None)
    cost = sum(r["tokens_in"] * price_in + r["tokens_out"] * price_out for r in rows) / 1_000_000
    return {
        "n": n,
        "field_acc": {f: sum(r["pred"][f] == r["gold"][f] for r in rows) / n for f in FIELDS},
        "doc_acc": sum(all(r["pred"][f] == r["gold"][f] for f in FIELDS) for r in rows) / n,
        "silent_rate": sum(is_silent(p, g) for p, g in pairs) / n_fields,
        "null_rate": sum(p is None and g is not None for p, g in pairs) / n_fields,
        "halluc_rate": sum(p is not None for p, g in pairs if g is None) / gold_null if gold_null else 0.0,
        "silent_count": sum(is_silent(p, g) for p, g in pairs),
        "format_fail_rate": sum(bool(r.get("format_failed")) for r in rows) / n,
        "retry_rate": sum(r.get("retries", 0) > 0 for r in rows) / n,
        "latency_p50": percentile([r["latency_s"] for r in rows], 50),
        "latency_p95": percentile([r["latency_s"] for r in rows], 95),
        "cost_per_doc": cost / n,
        "tokens_per_doc": (sum(r["tokens_in"] for r in rows) / n, sum(r["tokens_out"] for r in rows) / n),
    }


def grouped(rows: list[dict], key: str, **price) -> dict[str, dict]:
    groups = collections.defaultdict(list)
    for r in rows:
        groups[r[key]].append(r)
    return {k: compute(v, **price) for k, v in sorted(groups.items())}
