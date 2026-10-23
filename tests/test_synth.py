import random
from decimal import Decimal

import pytest

from ocr_extract.schema import ReceiptFields
from ocr_extract.synth.degrade import LEVELS
from ocr_extract.synth.generate import TEMPLATES, make_sample
from ocr_extract.synth.templates import FONTS, has_glyph
from ocr_extract.synth.values import amount_to_chinese


@pytest.mark.parametrize(
    "value, expected",
    [
        ("12500.00", "壹万贰仟伍佰元整"),
        ("1005.05", "壹仟零伍元零伍分"),
        ("10.50", "壹拾元伍角整"),
        ("100.10", "壹佰元壹角整"),
        ("1.01", "壹元零壹分"),
        ("10005.00", "壹万零伍元整"),
        ("1000000.00", "壹佰万元整"),
        ("10000500.00", "壹仟万零伍佰元整"),
        ("9999999.99", "玖佰玖拾玖万玖仟玖佰玖拾玖元玖角玖分"),
    ],
)
def test_amount_to_chinese(value, expected):
    assert amount_to_chinese(Decimal(value)) == expected


CASES = [(t, i) for t in TEMPLATES for i in range(50)]


@pytest.mark.parametrize("template, i", CASES)
def test_label_is_canonical(template, i):
    r = TEMPLATES[template](random.Random(i), FONTS["simhei"])
    assert ReceiptFields.model_validate(r.fields).model_dump(mode="json") == r.fields


@pytest.mark.parametrize("template, i", CASES)
def test_rendered_normalizes_to_label(template, i):
    """图上的写法经过 schema 归一化后,必须等于独立构造的标准答案。"""
    r = TEMPLATES[template](random.Random(i), FONTS["simhei"])
    assert ReceiptFields.model_validate(r.rendered).model_dump(mode="json") == r.fields


@pytest.mark.parametrize("font_name", sorted(FONTS))
@pytest.mark.parametrize("template", sorted(TEMPLATES))
def test_no_missing_glyphs(template, font_name):
    """字体缺字会画成方框,OCR 读不出来,这样的样本对所有方案都不公平。"""
    path = FONTS[font_name]
    for i in range(20):
        r = TEMPLATES[template](random.Random(i), path)
        missing = {ch for s in r.texts for ch in s if not has_glyph(path, ch)}
        assert not missing, f"{font_name} 缺字: {sorted(map(hex, map(ord, missing)))}"


def test_statement_has_no_payee():
    for i in range(20):
        assert TEMPLATES["statement"](random.Random(i), FONTS["simhei"]).fields["payee_name"] is None


@pytest.mark.parametrize("level", LEVELS)
def test_reproducible(level):
    img1, label1 = make_sample("receipt", level, 0, seed=42)
    img2, label2 = make_sample("receipt", level, 0, seed=42)
    assert label1 == label2
    assert img1.tobytes() == img2.tobytes()


def test_samples_are_independent():
    """改种子只影响自己:不同 index 的样本不应相同。"""
    _, a = make_sample("invoice", "clean", 0, seed=42)
    _, b = make_sample("invoice", "clean", 1, seed=42)
    assert a["fields"] != b["fields"]
