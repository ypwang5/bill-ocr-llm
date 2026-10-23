import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ocr_extract.api import main
from ocr_extract.extractors.base import ExtractionResult

FIELDS = {"payer_name": "甲", "payee_name": None, "amount": "1.00", "date": "2026-01-01", "serial_no": "S1"}


def png(size=(60, 40)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, "white").save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def client(monkeypatch):
    seen = []

    def fake(method):
        def run(path):
            seen.append((method, path))
            return ExtractionResult(fields=FIELDS, latency_s=1.5, tokens_in=10, tokens_out=2,
                                    fallback=method == "D", route_reasons=["amount为空"] if method == "D" else [])
        return run

    # 不加载 Paddle、不调用大模型:接口测试只测接口本身
    monkeypatch.setattr(main, "warmup", lambda: None)
    monkeypatch.setattr(main, "build_extractors", lambda: {m: fake(m) for m in "ABCD"})
    with TestClient(main.app) as c:
        c.seen = seen
        yield c


def test_extract_ok_default_method_is_d(client):
    r = client.post("/extract", files={"file": ("a.png", png(), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert body["method"] == "D" and body["fields"] == FIELDS
    assert body["fallback"] is True and body["route_reasons"] == ["amount为空"]
    assert client.seen[0][1].suffix == ".png" and client.seen[0][1].exists()


def test_method_param(client):
    r = client.post("/extract", files={"file": ("a.png", png(), "image/png")}, data={"method": "A"})
    assert r.json()["method"] == "A" and r.json()["fallback"] is False
    assert client.post("/extract", files={"file": ("a.png", png(), "image/png")}, data={"method": "X"}).status_code == 422


def test_rejects_bad_uploads(client, monkeypatch):
    assert client.post("/extract", files={"file": ("a.pdf", b"%PDF", "application/pdf")}).status_code == 415
    assert client.post("/extract", files={"file": ("a.png", b"not an image", "image/png")}).status_code == 400
    monkeypatch.setattr(main, "MAX_BYTES", 100)
    assert client.post("/extract", files={"file": ("a.png", png((400, 400)), "image/png")}).status_code == 413
    assert client.seen == []  # 都在调用抽取之前就被拦下


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
