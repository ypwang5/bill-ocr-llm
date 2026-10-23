"""方案 C:多模态大模型直接看图抽取,不经过 OCR。

字段定义、校验、重试和方案 B 完全一样(chat_with_retry),差别只在输入是图片而不是 OCR 文本。
"""

import base64
import io
from pathlib import Path

from PIL import Image

from ocr_extract.llm.client import LLMClient

from .base import ExtractionResult
from .ocr_llm import chat_with_retry, load_prompt

# 实测(D23):token 随尺寸增长,最长边 512/1024/2048 约 210/440/1000 token,三者都能读对 20 位发票号。
# 测试集原图最长边都 ≤1276,所以原样发送,只给超大图设上限,不放大
MAX_SIDE = 1600


def image_to_data_url(image_path: Path, max_side: int = MAX_SIDE) -> str:
    im = Image.open(image_path).convert("RGB")
    if max(im.size) > max_side:
        im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "PNG")  # 无损:JPEG 压缩会糊掉小字和小数点
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


class VlmExtractor:
    def __init__(self, prompt_version: str = "v1", client: LLMClient | None = None):
        self.prompt, self.prompt_sha256 = load_prompt(prompt_version, name="vlm")
        self.client = client or LLMClient()

    def extract(self, image_path: Path) -> ExtractionResult:
        messages = [
            {"role": "system", "content": self.prompt["system.md"]},
            {"role": "user", "content": [
                {"type": "text", "text": self.prompt["user.md"]},
                {"type": "image_url", "image_url": {"url": image_to_data_url(image_path)}},
            ]},
        ]
        return chat_with_retry(self.client, messages, self.prompt["retry.md"], model=self.client.settings.model_vision)
