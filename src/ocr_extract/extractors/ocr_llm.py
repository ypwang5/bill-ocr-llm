"""方案 B:PaddleOCR 文本 + 大模型抽取。

OCR 和方案 A 读同一份缓存,两者的差别只来自"规则"和"LLM"。
"""

import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from ocr_extract.config import ROOT
from ocr_extract.llm.client import LLMClient
from ocr_extract.ocr.paddle_engine import ocr
from ocr_extract.schema import ReceiptFields

from .base import FIELDS, ExtractionResult, normalize_partial

PROMPT_FILES = ("system.md", "user.md", "retry.md")


def load_prompt(version: str) -> tuple[dict[str, str], str]:
    """返回三段提示词和它们的 sha256 指纹(写进实验配置,证明跑的是哪一版)。"""
    folder = ROOT / "prompts" / f"extract_{version}"
    parts = {name: (folder / name).read_text(encoding="utf-8") for name in PROMPT_FILES}
    digest = hashlib.sha256("".join(parts[n] for n in PROMPT_FILES).encode("utf-8")).hexdigest()
    return parts, digest


def validate(text: str) -> tuple[dict | None, dict | None, str | None]:
    """返回 (校验通过的字段, 解析出的原始 dict, 错误信息)。错误信息会原样发回给模型。"""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return None, None, f"不是合法的 JSON({e})"
    if not isinstance(data, dict):
        return None, None, "输出必须是一个 JSON 对象"
    try:
        return ReceiptFields.model_validate(data).model_dump(mode="json"), data, None
    except ValidationError as e:
        msgs = [f"{'.'.join(map(str, err['loc'])) or '整体'}: {err['msg']}" for err in e.errors()]
        return None, data, ";".join(msgs)


class OcrLlmExtractor:
    def __init__(self, prompt_version: str = "v1", client: LLMClient | None = None, use_doc_unwarping: bool = True):
        self.prompt, self.prompt_sha256 = load_prompt(prompt_version)
        self.client = client or LLMClient()
        self.use_doc_unwarping = use_doc_unwarping

    def extract(self, image_path: Path) -> ExtractionResult:
        result = ocr(image_path, self.use_doc_unwarping)
        # 用 replace 而不是 str.format:提示词里有 JSON 的花括号
        messages = [
            {"role": "system", "content": self.prompt["system.md"]},
            {"role": "user", "content": self.prompt["user.md"].replace("{ocr_text}", result.text)},
        ]
        outputs, llm_s, t_in, t_out = [], 0.0, 0, 0
        for attempt in range(2):  # 首次 + 重试一次
            resp = self.client.chat(messages)
            outputs.append({"text": resp.text, "reasoning_tokens": resp.reasoning_tokens, "model": resp.model})
            llm_s, t_in, t_out = llm_s + resp.latency_s, t_in + resp.tokens_in, t_out + resp.tokens_out
            fields, data, error = validate(resp.text)
            if error is None:
                break
            outputs[-1]["error"] = error
            # 把模型自己的输出和错误原因都带上,让它知道错在哪
            messages += [
                {"role": "assistant", "content": resp.text},
                {"role": "user", "content": self.prompt["retry.md"].replace("{error}", error)},
            ]

        field_errors: dict[str, str] = {}
        if error is not None:
            # 降级:和方案 A 一样只丢坏字段;连 JSON 都不是就全部置 null
            if data is not None:
                fields, field_errors = normalize_partial({k: data.get(k) for k in FIELDS})
            else:
                fields = dict.fromkeys(FIELDS)
                field_errors = dict.fromkeys(FIELDS, error)

        return ExtractionResult(
            fields=fields,
            field_errors=field_errors,
            latency_s=result.latency_s + llm_s,
            ocr_latency_s=result.latency_s,
            tokens_in=t_in,
            tokens_out=t_out,
            raw_output=json.dumps(outputs, ensure_ascii=False),
            retries=attempt,
            format_failed=error is not None,
        )
