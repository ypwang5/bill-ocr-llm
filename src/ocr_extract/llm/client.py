"""统一的 LLM 调用:OpenAI 兼容接口。换云端模型或本地 vLLM/Ollama 只改 .env 的 base_url 和模型名。"""

import time
from dataclasses import dataclass

from openai import OpenAI

from ocr_extract.config import Settings, load_settings


@dataclass
class LLMResponse:
    text: str
    latency_s: float
    tokens_in: int
    tokens_out: int  # 含思考 token:计费按它算
    reasoning_tokens: int  # 其中用于"思考"的部分,单独记下看模型是否默认开启思考
    model: str


class LLMClient:
    def __init__(self, settings: Settings | None = None, timeout_s: float = 60) -> None:
        self.settings = settings or load_settings()
        # max_retries 只管网络错误/限流(SDK 自动退避重试);输出格式不对的重试在 extractor 里,两者分开统计
        self._client = OpenAI(
            api_key=self.settings.api_key, base_url=self.settings.base_url, timeout=timeout_s, max_retries=2
        )

    def chat(self, messages: list[dict], model: str | None = None, json_mode: bool = True) -> LLMResponse:
        model = model or self.settings.model_text
        kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
        t = time.perf_counter()
        # temperature=0:抽取任务要的是稳定,不是创意
        resp = self._client.chat.completions.create(model=model, messages=messages, temperature=0, **kwargs)
        latency = time.perf_counter() - t
        usage = resp.usage
        details = usage.completion_tokens_details if usage else None
        return LLMResponse(
            text=resp.choices[0].message.content or "",
            latency_s=latency,
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
            reasoning_tokens=(details.reasoning_tokens or 0) if details else 0,
            model=resp.model,
        )


def cost(tokens_in: int, tokens_out: int, price_in: float, price_out: float) -> float:
    """按每百万 token 单价估算一次调用的费用(单位跟 .env 里填的价格一致)。"""
    return (tokens_in * price_in + tokens_out * price_out) / 1_000_000
