"""方案 D:融合路由。先走 B(OCR + LLM),B 报告"不确定"时才调用 C(多模态)。

依据 2.1/2.2 的数据:B 出错时大多是 null(能发现),C 出错时是静默错误。
所以 B 能给出的"不确定"信号就是回退的开关,C 只用来补 B 的空。
路由和合并都是纯函数,在线运行和"用已存预测回放"走同一套代码。
"""

import re
import unicodedata
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path

from ocr_extract.ocr.paddle_engine import OcrResult, ocr
from ocr_extract.synth.values import amount_to_chinese

from .base import FIELDS, ExtractionResult


@dataclass(frozen=True)
class RouteConfig:
    # 默认值 = 调参集(dev 18 + tune 36)上按 D24 规则选中的配置,见 D25
    min_mean_score: float = 0.0  # OCR 平均置信度低于它就回退;0 表示不用这个信号
    check_daxie: bool = False  # 单据上有大写金额时,和 B 的金额交叉校验
    merge: str = "fill"  # fill:只补 B 的空;replace:整单用 C;agree:补空,且 B、C 冲突时置 null 转人工
    check_serial: bool = False  # 编号格式校验:B 的编号不合格式就回退;C 补进来的编号不合格式就不要


# 业务规则:各票种编号的固定格式。真实场景按银行/票种配置。
# 这条来自 2.3 对测试集的错误分析(C 的编号常漏位),只作为候选,用不用由调参集决定(D25)
SERIAL_PATTERNS = [re.compile(p) for p in (r"\d{20}", r"HX\d{14}", r"DZ\d{12}")]


def serial_ok(value: str | None) -> bool:
    return value is None or any(p.fullmatch(value) for p in SERIAL_PATTERNS)


# 第二套配置:同一调参集上"静默错误最少"的那组。宁可多转人工,也要少出静默错误(D25)
SAFE_CONFIG = RouteConfig(min_mean_score=0.97, merge="agree")


def _flat(text: str) -> str:
    return "".join(unicodedata.normalize("NFKC", text).split())


def route_reasons(b: ExtractionResult, ocr_result: OcrResult, cfg: RouteConfig) -> list[str]:
    reasons = []
    if b.format_failed or b.field_errors:
        reasons.append("校验失败")
    text = _flat(ocr_result.text)
    # 对账单没有收款人(D12),payee 为 null 是正常的,不算信号
    required = [f for f in FIELDS if not (f == "payee_name" and "对账单" in text)]
    reasons += [f"{f}为空" for f in required if b.fields[f] is None]
    scores = [l.score for l in ocr_result.lines]
    if cfg.min_mean_score and scores and sum(scores) / len(scores) < cfg.min_mean_score:
        reasons.append("OCR置信度低")
    # 有"大写"但找不到 B 金额对应的大写写法 → 小写可能读错了(或大写那行本身被认错,宁可多回退)
    if cfg.check_daxie and "大写" in text and b.fields["amount"] is not None:
        if amount_to_chinese(Decimal(b.fields["amount"])) not in text:
            reasons.append("大小写金额不一致")
    if cfg.check_serial and not serial_ok(b.fields["serial_no"]):
        reasons.append("编号格式不对")
    return reasons


def merge(b: dict, c: dict, strategy: str, check_serial: bool = False) -> dict:
    if check_serial:
        b = {**b, "serial_no": b["serial_no"] if serial_ok(b["serial_no"]) else None}
        c = {**c, "serial_no": c["serial_no"] if serial_ok(c["serial_no"]) else None}
    if strategy == "replace":
        return dict(c)
    out = {}
    for f in FIELDS:
        if b[f] is None:
            out[f] = c[f]
        elif strategy == "agree" and c[f] is not None and c[f] != b[f]:
            out[f] = None  # 两个方案说法不一,谁也不信,交给人工
        else:
            out[f] = b[f]
    return out


def combine(b: ExtractionResult, c: ExtractionResult | None, reasons: list[str], cfg: RouteConfig) -> ExtractionResult:
    if c is None:
        return replace(b, fallback=False, route_reasons=[])
    return ExtractionResult(
        fields=merge(b.fields, c.fields, cfg.merge, cfg.check_serial),
        field_errors={},
        latency_s=b.latency_s + c.latency_s,  # 串行:先 B 后 C
        ocr_latency_s=b.ocr_latency_s,
        tokens_in=b.tokens_in + c.tokens_in,
        tokens_out=b.tokens_out + c.tokens_out,
        raw_output=f'{{"B": {b.raw_output or "null"}, "C": {c.raw_output or "null"}}}',
        retries=b.retries + c.retries,
        format_failed=c.format_failed and b.format_failed,
        fallback=True,
        route_reasons=reasons,
    )


class HybridExtractor:
    def __init__(self, cfg: RouteConfig = RouteConfig(), b=None, c=None, use_doc_unwarping: bool = True):
        if b is None or c is None:
            from .ocr_llm import OcrLlmExtractor
            from .vlm_direct import VlmExtractor
            b, c = b or OcrLlmExtractor().extract, c or VlmExtractor().extract
        self.cfg, self.b, self.c, self.unwarp = cfg, b, c, use_doc_unwarping

    @classmethod
    def from_predictions(cls, preds: dict[str, list[dict]], cfg: RouteConfig = RouteConfig()) -> "HybridExtractor":
        """回放:用已经存下的 B、C 预测代替真实调用,调阈值时不花钱。C 只在被路由到时才计入成本和耗时。"""
        def lookup(method):
            table = {r["id"]: r for r in preds[method]}
            keep = ExtractionResult.__dataclass_fields__
            return lambda path: ExtractionResult(**{k: v for k, v in table[Path(path).stem].items() if k in keep})
        return cls(cfg, b=lookup("B"), c=lookup("C"))

    def extract(self, image_path: Path) -> ExtractionResult:
        b = self.b(image_path)
        reasons = route_reasons(b, ocr(image_path, self.unwarp), self.cfg)
        c = self.c(image_path) if reasons else None
        return combine(b, c, reasons, self.cfg)
