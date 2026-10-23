"""方案 A:PaddleOCR + 关键词/位置规则。

规则拿不到模板名,只看 OCR 文字和坐标,和其他方案一样只拿到一张图。
规则是只看开发集(seed=7)写的,测试集(seed=42)只用来报告结果。
"""

import json
import re
import time
import unicodedata
from pathlib import Path

from ocr_extract.ocr.paddle_engine import OcrLine, OcrResult, ocr

from .base import ExtractionResult, normalize_partial

# 关键词按优先级排列;都是"标签:值"里的标签部分
KEYS = {
    "amount": ["小写", "期末余额"],  # 排除"金额""税额""期初余额":它们是干扰项
    "date": ["交易日期", "开票日期", "对账截止日"],
    "serial_no": ["流水号", "发票号码", "对账单编号"],
}
PAYER_HEADERS, PAYEE_HEADERS = ["付款方", "购买方"], ["收款方", "销售方"]
NAME_KEYS = ["户名", "名称"]

_COLON = re.compile("[:" + chr(0xFF1A) + "]")  # 半角和全角冒号;用 chr 避免转义写错


def _norm(s: str) -> str:
    return re.sub(r"\s", "", unicodedata.normalize("NFKC", s))


def _split(line: OcrLine) -> tuple[str, str | None]:
    """'户名:云帆贸易' → ('户名', '云帆贸易');没有冒号时返回 (整行, None)。"""
    text = unicodedata.normalize("NFKC", line.text)
    parts = _COLON.split(text, maxsplit=1)
    return (_norm(parts[0]), parts[1].strip()) if len(parts) == 2 else (_norm(text), None)


def _right_neighbor(line: OcrLine, lines: list[OcrLine]) -> OcrLine | None:
    """同一行、在右边、最近的框。坐标是摆正后的,所以倾斜不影响同行判断。"""
    same_row = [
        o for o in lines
        if o is not line and abs(o.cy - line.cy) < 0.5 * min(o.height, line.height) and o.box[0] >= line.box[2] - 5
    ]
    return min(same_row, key=lambda o: o.box[0], default=None)


def _value_after(line: OcrLine, lines: list[OcrLine]) -> str | None:
    key, value = _split(line)
    if value:
        return value
    nb = _right_neighbor(line, lines)
    return _COLON.sub("", nb.text).strip() if nb else None


def find_value(keys: list[str], lines: list[OcrLine]) -> tuple[str | None, OcrLine | None]:
    for k in keys:
        for line in lines:
            if k in _split(line)[0]:
                return _value_after(line, lines), line
    return None, None


def find_party(headers: list[str], lines: list[OcrLine]) -> tuple[str | None, OcrLine | None]:
    """区块标题(付款方/购买方)下方、同一栏里最近的"户名/名称"。"""
    head = next((l for l in lines if any(_norm(l.text).startswith(h) for h in headers)), None)
    if head is None:
        return None, None
    tol = 2 * head.height
    below = [
        l for l in lines
        if l.box[1] > head.box[1] and abs(l.box[0] - head.box[0]) < tol and any(_split(l)[0].endswith(k) for k in NAME_KEYS)
    ]
    line = min(below, key=lambda l: l.box[1], default=None)
    return (_value_after(line, lines), line) if line else (None, None)


def extract_from_ocr(result: OcrResult) -> tuple[dict[str, str | None], dict[str, str]]:
    lines = result.lines
    raw, hits = {}, {}
    for name, keys in KEYS.items():
        raw[name], hit = find_value(keys, lines)
        hits[name] = hit.text if hit else None

    raw["payer_name"], hit = find_party(PAYER_HEADERS, lines)
    # 没有付款/收款区块时(对账单),唯一的"户名"就是账户户名。
    # 但开发集里水印盖掉了回单的区块标题和付款方户名,只剩收款方户名,被当成了付款人(静默错误)。
    # 所以要求图上只有"一方":"账号"最多出现一次。两方的票据上剩一个户名,分不清归谁 → null
    name_lines = [l for l in lines if _split(l)[0] == "户名"]  # 精确匹配,排除表头"对方户名"
    account_lines = [l for l in lines if _split(l)[0].endswith("账号")]
    if hit is None and len(name_lines) == 1 and len(account_lines) <= 1:
        raw["payer_name"], hit = _value_after(name_lines[0], lines), name_lines[0]
    hits["payer_name"] = hit.text if hit else None

    # 找不到收款区块就是 null,不从明细里猜
    raw["payee_name"], hit = find_party(PAYEE_HEADERS, lines)
    hits["payee_name"] = hit.text if hit else None
    return raw, hits


_HAS_CENTS = re.compile(r"\.\d{2}$")


def extract(image_path: Path, use_doc_unwarping: bool = True) -> ExtractionResult:
    t = time.perf_counter()
    result = ocr(image_path, use_doc_unwarping)
    ocr_wall = time.perf_counter() - t
    raw, hits = extract_from_ocr(result)
    fields, errors = normalize_partial(raw)
    # 票据上打印的金额都带角分。OCR 读出来没有,说明数字被印章从小数点处拆断或漏读了
    # (开发集:"RMB220,957" + "09" 被当成 220957.00)。这条只用于 OCR 文本,schema 仍接受 12500
    if fields["amount"] is not None and not _HAS_CENTS.search(_norm(raw["amount"] or "")):
        errors["amount"] = f"OCR 金额缺少角分,可能被拆断: {raw['amount']!r}"
        fields["amount"] = None
    # 读缓存时 OCR 几乎不耗时,总耗时用缓存里记录的首次 OCR 耗时 + 规则耗时
    rule_s = time.perf_counter() - t - ocr_wall
    return ExtractionResult(
        fields=fields,
        field_errors=errors,
        latency_s=result.latency_s + rule_s,
        ocr_latency_s=result.latency_s,
        raw_output=json.dumps({"raw": raw, "hit_lines": hits}, ensure_ascii=False),
    )
