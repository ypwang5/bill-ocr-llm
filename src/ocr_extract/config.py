"""从 .env 读配置。Key 只在这里读进内存,不打印、不写进结果文件。"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str
    model_text: str
    model_vision: str
    price_text_in: float  # 每百万 token 的价格
    price_text_out: float
    price_vision_in: float
    price_vision_out: float

    def public(self) -> dict:
        """写进实验配置快照的部分:不含 Key。"""
        return {k: v for k, v in self.__dict__.items() if k != "api_key"}


def load_settings() -> Settings:
    # override=False:终端里显式设置的环境变量优先,方便临时切换模型
    load_dotenv(ROOT / ".env", override=False)

    def need(name: str) -> str:
        value = os.environ.get(name, "").strip()
        if not value:
            raise RuntimeError(f".env 缺少 {name}")
        return value

    return Settings(
        base_url=need("LLM_BASE_URL"),
        api_key=need("LLM_API_KEY"),
        model_text=need("LLM_MODEL_TEXT"),
        model_vision=need("LLM_MODEL_VISION"),
        price_text_in=float(need("PRICE_TEXT_IN")),
        price_text_out=float(need("PRICE_TEXT_OUT")),
        price_vision_in=float(need("PRICE_VISION_IN")),
        price_vision_out=float(need("PRICE_VISION_OUT")),
    )
