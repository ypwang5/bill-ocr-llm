"""抽取字段的定义、归一化与校验。

归一化函数是纯函数,schema、合成样本生成器、规则抽取共用同一套规则。
无法解析时一律抛 ValueError,不返回 None:静默变成 null 的错误
既不会触发重试,也不会让融合路由回退(见 docs/decisions.md D8)。
"""

import datetime as dt
import re
import unicodedata
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

_NULL_TOKENS = {"", "null", "none", "n/a", "无"}

_CURRENCY = re.compile(r"人民币|RMB|CNY|[¥元]", re.IGNORECASE)
# 逗号必须是标准千分位:防止小数点被 OCR 认成逗号(12,500,00)后删逗号放大 100 倍
_AMOUNT = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?")

_TIME_TAIL = r"(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?"
# 只接受"年在前"的写法:03/04/2026 分不清月日,猜错比报错更糟
_DATE_SEP = re.compile(r"(\d{4})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})\s*日?" + _TIME_TAIL)
_DATE_COMPACT = re.compile(r"(\d{4})(\d{2})(\d{2})")

_SERIAL = re.compile(r"[A-Z0-9-]+")


def _clean(raw: object) -> str | None:
    """NFKC 统一全角/半角(1.2 实测 OCR 会把半角冒号输出成全角),再去首尾空白。"""
    if raw is None:
        return None
    text = unicodedata.normalize("NFKC", str(raw)).strip()
    return None if text.lower() in _NULL_TOKENS else text


def normalize_name(raw: object) -> str | None:
    return _clean(raw)


def normalize_amount(raw: object) -> Decimal | None:
    text = _clean(raw)
    if text is None:
        return None
    text = re.sub(r"\s", "", _CURRENCY.sub("", text))
    if not _AMOUNT.fullmatch(text):
        raise ValueError(f"无法解析的金额: {raw!r}")
    value = Decimal(text.replace(",", "")).quantize(Decimal("0.01"))
    if value <= 0:
        raise ValueError(f"金额必须大于 0: {raw!r}")
    return value


def normalize_date(raw: object) -> dt.date | None:
    if isinstance(raw, dt.datetime):
        return raw.date()
    if isinstance(raw, dt.date):
        return raw
    text = _clean(raw)
    if text is None:
        return None
    m = _DATE_SEP.fullmatch(text) or _DATE_COMPACT.fullmatch(text)
    if not m:
        raise ValueError(f"无法解析的日期: {raw!r}")
    try:
        return dt.date(*(int(g) for g in m.groups()))
    except ValueError:
        raise ValueError(f"不存在的日期: {raw!r}") from None


def normalize_serial(raw: object) -> str | None:
    text = _clean(raw)
    if text is None:
        return None
    text = re.sub(r"\s", "", text).upper()
    if not _SERIAL.fullmatch(text):
        raise ValueError(f"流水号含非法字符: {raw!r}")
    return text


class ReceiptFields(BaseModel):
    # forbid:模型把 payer_name 拼成 payer 时报错,而不是悄悄当成"没找到"
    model_config = ConfigDict(extra="forbid")

    # 不给默认值:5 个键必须都出现,"找过但没有"要显式写 null
    payer_name: str | None
    payee_name: str | None
    amount: Decimal | None
    date: dt.date | None
    serial_no: str | None

    @field_validator("payer_name", "payee_name", mode="before")
    @classmethod
    def _name(cls, v: object) -> str | None:
        return normalize_name(v)

    @field_validator("amount", mode="before")
    @classmethod
    def _amount(cls, v: object) -> Decimal | None:
        return normalize_amount(v)

    @field_validator("date", mode="before")
    @classmethod
    def _date(cls, v: object) -> dt.date | None:
        return normalize_date(v)

    @field_validator("serial_no", mode="before")
    @classmethod
    def _serial(cls, v: object) -> str | None:
        return normalize_serial(v)
