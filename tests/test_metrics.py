import pytest

from ocr_extract.eval.metrics import compute, grouped, percentile

GOLD = {"payer_name": "甲", "payee_name": None, "amount": "1.00", "date": "2026-01-01", "serial_no": "S1"}


def row(difficulty="clean", latency=1.0, tokens=(100, 10), **pred):
    return {"difficulty": difficulty, "pred": {**GOLD, **pred}, "gold": GOLD, "latency_s": latency,
            "tokens_in": tokens[0], "tokens_out": tokens[1], "retries": 0, "format_failed": False}


def test_all_correct():
    m = compute([row(), row()])
    assert m["doc_acc"] == 1 and all(v == 1 for v in m["field_acc"].values())
    assert m["silent_rate"] == m["null_rate"] == m["halluc_rate"] == 0


def test_error_kinds_are_separated():
    rows = [
        row(amount="2.00"),  # 静默错误
        row(date=None),  # 留空:可检测
        row(payee_name="乙"),  # 幻觉:答案是 null 却输出了值,同时也是静默错误
        row(),
    ]
    m = compute(rows)
    assert m["doc_acc"] == 0.25
    assert m["field_acc"]["amount"] == 0.75 and m["field_acc"]["payee_name"] == 0.75
    assert m["silent_count"] == 2 and m["silent_rate"] == 2 / 20
    assert m["null_rate"] == 1 / 20
    assert m["halluc_rate"] == 1 / 4  # 4 张单据的 payee 都是 null,其中 1 张被编了


def test_null_matching_null_is_correct():
    assert compute([row()])["field_acc"]["payee_name"] == 1


def test_cost_and_format():
    rows = [row(tokens=(1_000_000, 0)), {**row(tokens=(0, 1_000_000)), "retries": 1, "format_failed": True}]
    m = compute(rows, price_in=1, price_out=4)
    assert m["cost_per_doc"] == pytest.approx(2.5)
    assert m["retry_rate"] == m["format_fail_rate"] == 0.5


def test_percentile():
    assert percentile(list(range(1, 101)), 50) == pytest.approx(50.5)
    assert percentile([3.0], 95) == 3.0 and percentile([], 50) == 0.0
    assert percentile([float(x) for x in range(1, 21)], 95) == pytest.approx(19.05)


def test_grouped():
    g = grouped([row("blur", amount="9.00"), row("clean")], "difficulty")
    assert g["blur"]["doc_acc"] == 0 and g["clean"]["doc_acc"] == 1
