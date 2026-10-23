import datetime as dt
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ocr_extract.schema import (
    ReceiptFields,
    normalize_amount,
    normalize_date,
    normalize_name,
    normalize_serial,
)

NULLS = [None, "", "  ", "null", "NULL", "None", "N/A", "无"]


@pytest.mark.parametrize("fn", [normalize_name, normalize_amount, normalize_date, normalize_serial])
@pytest.mark.parametrize("raw", NULLS)
def test_null_tokens(fn, raw):
    assert fn(raw) is None


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("  星河科技有限公司 ", "星河科技有限公司"),
        ("　星河科技有限公司　", "星河科技有限公司"),  # 全角空格
        ("星河科技\uff08北京\uff09有限公司", "星河科技(北京)有限公司"),  # 全角括号 → 半角
    ],
)
def test_name(raw, expected):
    assert normalize_name(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("12500.00", "12500.00"),
        ("12,500.00", "12500.00"),  # 1.2 实测:OCR 漏掉 ¥
        ("¥12,500.00", "12500.00"),
        ("\uffe512,500.00", "12500.00"),  # 全角 ¥
        ("RMB 12,500.00", "12500.00"),
        ("人民币12500元", "12500.00"),
        ("12500", "12500.00"),
        ("12500.5", "12500.50"),
        ("1,234,567.89", "1234567.89"),
        ("\uff11\uff12\uff0c\uff15\uff10\uff10\uff0e\uff10\uff10", "12500.00"),  # 全角数字和标点
        (Decimal("12500.0"), "12500.00"),
        (12500, "12500.00"),  # LLM 可能输出数字而不是字符串
    ],
)
def test_amount_ok(raw, expected):
    assert normalize_amount(raw) == Decimal(expected)


@pytest.mark.parametrize(
    "raw",
    [
        "12,5OO.00",  # 0 被认成字母 O
        "12,500,00",  # 小数点被认成逗号:直接删逗号会放大 100 倍
        "1,2500.00",  # 千分位位置不对
        "12500.005",  # 超过 2 位小数:说明认错了,不四舍五入
        "0",
        "0.00",
        "-500.00",
        "12.500,00",  # 欧式写法
        "壹万贰仟伍佰元整",  # 大写金额本步不处理
    ],
)
def test_amount_rejected(raw):
    with pytest.raises(ValueError):
        normalize_amount(raw)


@pytest.mark.parametrize(
    "raw",
    [
        "2026-03-15",
        "2026/3/15",
        "2026.03.15",
        "2026年3月15日",
        "2026 年 03 月 15 日",
        "20260315",
        "2026-03-15 14:23:01",
        "2026/03/15 9:05",
        "\uff12\uff10\uff12\uff16\uff0d\uff10\uff13\uff0d\uff11\uff15",  # 全角
        dt.date(2026, 3, 15),
        dt.datetime(2026, 3, 15, 14, 23),
    ],
)
def test_date_ok(raw):
    assert normalize_date(raw) == dt.date(2026, 3, 15)


@pytest.mark.parametrize(
    "raw",
    [
        "2026-02-30",  # 不存在
        "2026-13-01",
        "03/04/2026",  # 月日不明
        "26-03-15",  # 两位年份
        "2026-03-15abc",
        "2O26-03-15",  # 0 被认成 O
    ],
)
def test_date_rejected(raw):
    with pytest.raises(ValueError):
        normalize_date(raw)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("HX20260315001", "HX20260315001"),
        (" hx 2026 0315 001 ", "HX20260315001"),
        ("HX-2026-001", "HX-2026-001"),
        ("HX20260315O001", "HX20260315O001"),  # 不做 O→0:流水号本来就可能有字母
        ("\uff28\uff38\uff12\uff10\uff12\uff16", "HX2026"),  # 全角
    ],
)
def test_serial_ok(raw, expected):
    assert normalize_serial(raw) == expected


@pytest.mark.parametrize("raw", ["流水号:HX2026", "HX_2026", "HX#2026"])
def test_serial_rejected(raw):
    with pytest.raises(ValueError):
        normalize_serial(raw)


VALID = {
    "payer_name": " 星河科技\uff08北京\uff09有限公司",
    "payee_name": "云帆贸易有限公司",
    "amount": "¥12,500.00",
    "date": "2026年3月15日",
    "serial_no": "hx20260315001",
}


def test_model_normalizes_and_serializes():
    fields = ReceiptFields.model_validate(VALID)
    # 标签 JSON 的格式:金额是字符串(不经过 float),日期是 YYYY-MM-DD
    assert fields.model_dump(mode="json") == {
        "payer_name": "星河科技(北京)有限公司",
        "payee_name": "云帆贸易有限公司",
        "amount": "12500.00",
        "date": "2026-03-15",
        "serial_no": "HX20260315001",
    }


def test_model_json_roundtrip():
    fields = ReceiptFields.model_validate(VALID)
    assert ReceiptFields.model_validate_json(fields.model_dump_json()) == fields


def test_model_all_null():
    fields = ReceiptFields.model_validate({k: None for k in VALID})
    assert all(v is None for v in fields.model_dump().values())


def test_model_reports_every_bad_field():
    bad = {**VALID, "amount": "12,500,00", "date": "2026-02-30"}
    with pytest.raises(ValidationError) as exc:
        ReceiptFields.model_validate(bad)
    assert {e["loc"][0] for e in exc.value.errors()} == {"amount", "date"}


def test_model_rejects_misspelled_key():
    bad = {k: v for k, v in VALID.items() if k != "payer_name"} | {"payer": "星河科技"}
    with pytest.raises(ValidationError) as exc:
        ReceiptFields.model_validate(bad)
    error_types = {(e["loc"][0], e["type"]) for e in exc.value.errors()}
    assert error_types == {("payer", "extra_forbidden"), ("payer_name", "missing")}


def test_model_requires_explicit_null():
    with pytest.raises(ValidationError):
        ReceiptFields.model_validate({k: v for k, v in VALID.items() if k != "serial_no"})
