import math

import pytest

from ocr_extract.extractors.base import normalize_partial
from ocr_extract.extractors.rule_based import _right_neighbor, find_value
from ocr_extract.ocr.paddle_engine import build_lines, estimate_skew


def _rot(poly, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[x * c - y * s, x * s + y * c] for x, y in poly]


def _box(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


# 1.2 Q1 的场景:"金额"和值是两个框,相距约 300px;下一行是日期
KEY = _box(40, 200, 100, 230)
VALUE = _box(400, 200, 540, 230)
NEXT_KEY = _box(40, 260, 100, 290)
NEXT_VALUE = _box(400, 260, 540, 290)


@pytest.mark.parametrize("deg", [0, 5, -8, 15])
def test_estimate_skew(deg):
    polys = [_rot(p, deg) for p in (KEY, VALUE, NEXT_KEY, NEXT_VALUE)]
    assert estimate_skew(polys) == pytest.approx(deg, abs=0.01)


@pytest.mark.parametrize("deg", [0, 15, -15])
def test_pairing_survives_rotation(deg):
    """不摆正时,15° 下右边的框会偏约 80px,配到下一行去;摆正后应仍配对正确。"""
    texts = ["金额", "12,500.00", "日期", "2026-03-15"]
    polys = [_rot(p, deg) for p in (KEY, VALUE, NEXT_KEY, NEXT_VALUE)]
    lines, _ = build_lines(texts, [1.0] * 4, polys)
    assert [l.text for l in lines] == texts  # 阅读顺序
    key = next(l for l in lines if l.text == "金额")
    assert _right_neighbor(key, lines).text == "12,500.00"
    assert find_value(["日期"], lines)[0] == "2026-03-15"


def test_normalize_partial_keeps_good_fields():
    fields, errors = normalize_partial({"payer_name": "星河科技", "amount": "12,500,00", "date": "2026-03-15"})
    assert fields == {"payer_name": "星河科技", "payee_name": None, "amount": None, "date": "2026-03-15", "serial_no": None}
    assert set(errors) == {"amount"}
