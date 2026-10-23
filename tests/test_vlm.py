import base64
import io
import json
from types import SimpleNamespace

from PIL import Image

from ocr_extract.extractors.vlm_direct import VlmExtractor, image_to_data_url
from ocr_extract.llm.client import LLMResponse


def _decode(url: str) -> Image.Image:
    assert url.startswith("data:image/png;base64,")
    return Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))


def test_image_kept_or_shrunk(tmp_path):
    small, big = tmp_path / "s.png", tmp_path / "b.png"
    Image.new("RGB", (1000, 620), "white").save(small)
    Image.new("RGB", (3200, 1600), "white").save(big)
    assert _decode(image_to_data_url(small)).size == (1000, 620)  # 不放大
    assert _decode(image_to_data_url(big)).size == (1600, 800)  # 等比缩小


def test_uses_vision_model_and_sends_image(tmp_path):
    img = tmp_path / "x.png"
    Image.new("RGB", (100, 50), "white").save(img)
    calls = []

    class Fake:
        settings = SimpleNamespace(model_vision="vision-model")

        def chat(self, messages, model=None):
            calls.append((messages, model))
            reply = {"payer_name": None, "payee_name": None, "amount": "1.00", "date": None, "serial_no": None}
            return LLMResponse(json.dumps(reply), 1.0, 500, 20, 0, model)

    r = VlmExtractor(client=Fake()).extract(img)
    messages, model = calls[0]
    assert model == "vision-model"
    assert messages[1]["content"][1]["type"] == "image_url"
    assert r.fields["amount"] == "1.00" and r.ocr_latency_s == 0
