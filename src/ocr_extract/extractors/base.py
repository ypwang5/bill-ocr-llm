"""所有 extractor 的统一输出,评估脚本只认这一种格式。"""

from dataclasses import dataclass, field

from ocr_extract.schema import (
    ReceiptFields,
    normalize_amount,
    normalize_date,
    normalize_name,
    normalize_serial,
)

FIELDS = ("payer_name", "payee_name", "amount", "date", "serial_no")
_NORMALIZERS = {
    "payer_name": normalize_name,
    "payee_name": normalize_name,
    "amount": normalize_amount,
    "date": normalize_date,
    "serial_no": normalize_serial,
}


@dataclass
class ExtractionResult:
    fields: dict[str, str | None]  # 与标签同格式(ReceiptFields 的 JSON 序列化)
    field_errors: dict[str, str] = field(default_factory=dict)  # 校验失败的字段及原因
    latency_s: float = 0.0
    ocr_latency_s: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    raw_output: str = ""


def normalize_partial(raw: dict[str, str | None]) -> tuple[dict[str, str | None], dict[str, str]]:
    """逐字段归一化:坏字段置 None 并记录原因,好字段照常保留(D8 的"只丢坏字段")。"""
    ok, errors = {}, {}
    for name in FIELDS:
        try:
            ok[name] = _NORMALIZERS[name](raw.get(name))
        except ValueError as e:
            ok[name], errors[name] = None, str(e)
    return ReceiptFields(**ok).model_dump(mode="json"), errors
