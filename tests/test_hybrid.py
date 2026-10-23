from decimal import Decimal

from ocr_extract.extractors.base import ExtractionResult
from ocr_extract.extractors.hybrid import HybridExtractor, RouteConfig, merge, route_reasons
from ocr_extract.extractors import hybrid
from ocr_extract.ocr.paddle_engine import OcrLine, OcrResult
from ocr_extract.synth.values import amount_to_chinese

FULL = {"payer_name": "甲公司", "payee_name": "乙公司", "amount": "12500.00", "date": "2026-03-15", "serial_no": "HX1"}


def ocr_of(*texts, score=0.99):
    lines = [OcrLine(t, score, [[0, i * 40], [100, i * 40], [100, i * 40 + 30], [0, i * 40 + 30]], (0, i * 40, 100, i * 40 + 30))
             for i, t in enumerate(texts)]
    return OcrResult(lines, 0.0, 20.0, {})


def b_result(**fields):
    return ExtractionResult(fields={**FULL, **fields}, latency_s=21.0, ocr_latency_s=20.0, tokens_in=900, tokens_out=200)


DAXIE = "金额(大写):" + amount_to_chinese(Decimal("12500.00"))


def test_confident_b_does_not_fall_back():
    assert route_reasons(b_result(), ocr_of("电子回单", DAXIE), RouteConfig()) == []


def test_signals():
    cfg = RouteConfig(min_mean_score=0.95, check_daxie=True)  # 默认值按 D25 改成了 False,这里显式打开
    assert "amount为空" in route_reasons(b_result(amount=None), ocr_of("回单"), cfg)
    assert "OCR置信度低" in route_reasons(b_result(), ocr_of("回单", score=0.8), cfg)
    # 大写写的是 12500,B 却读成 1250 → 交叉校验不过
    assert "大小写金额不一致" in route_reasons(b_result(amount="1250.00"), ocr_of(DAXIE), cfg)
    bad = b_result()
    bad.field_errors = {"date": "x"}
    assert "校验失败" in route_reasons(bad, ocr_of("回单"), cfg)


def test_statement_payee_null_is_not_a_signal():
    assert route_reasons(b_result(payee_name=None), ocr_of("星海银行账户对账单"), RouteConfig()) == []
    assert route_reasons(b_result(payee_name=None), ocr_of("电子回单"), RouteConfig()) == ["payee_name为空"]


def test_merge_strategies():
    b = {**FULL, "amount": None, "payer_name": "漏川"}
    c = {**FULL, "amount": "9.00", "payer_name": "澜川"}
    assert merge(b, c, "fill") == {**FULL, "amount": "9.00", "payer_name": "漏川"}  # 只补空
    assert merge(b, c, "agree") == {**FULL, "amount": "9.00", "payer_name": None}  # 冲突 → 人工
    assert merge(b, c, "replace") == c


def test_c_called_only_when_needed(monkeypatch):
    monkeypatch.setattr(hybrid, "ocr", lambda p, u: ocr_of("电子回单"))
    calls = []

    def c(path):
        calls.append(path)
        return ExtractionResult(fields={**FULL, "amount": "7.00"}, latency_s=2.0, tokens_in=1500, tokens_out=100)

    ok = HybridExtractor(RouteConfig(), b=lambda p: b_result(), c=c).extract("x.png")
    assert not calls and not ok.fallback and ok.tokens_in == 900

    d = HybridExtractor(RouteConfig(), b=lambda p: b_result(amount=None), c=c).extract("x.png")
    assert calls == ["x.png"] and d.fallback and d.fields["amount"] == "7.00"
    assert (d.latency_s, d.tokens_in, d.route_reasons) == (23.0, 2400, ["amount为空"])


def test_serial_format_check():
    from ocr_extract.extractors.hybrid import serial_ok
    assert serial_ok("35870897935485905905") and serial_ok("HX20250707044144") and serial_ok(None)
    assert not serial_ok("3587097935485905905") and not serial_ok("8X20250707044144")
    assert "编号格式不对" in route_reasons(b_result(serial_no="HX123"), ocr_of("电子回单"), RouteConfig(check_serial=True))
    # C 补进来的编号格式不对就不要,保持 null(可检测)
    b = {**FULL, "serial_no": None}
    assert merge(b, {**FULL, "serial_no": "8X20250707044144"}, "fill", check_serial=True)["serial_no"] is None
