import json

import pytest

from ocr_extract.extractors import ocr_llm
from ocr_extract.extractors.ocr_llm import OcrLlmExtractor, validate
from ocr_extract.llm.client import LLMResponse
from ocr_extract.ocr.paddle_engine import OcrResult

GOOD = {"payer_name": "星河科技", "payee_name": None, "amount": "12,500.00", "date": "2026/03/15", "serial_no": "hx01"}
GOOD_NORM = {"payer_name": "星河科技", "payee_name": None, "amount": "12500.00", "date": "2026-03-15", "serial_no": "HX01"}


@pytest.mark.parametrize("text, err_part", [
    ("不是 json", "JSON"),
    ("[1, 2]", "对象"),
    (json.dumps({**GOOD, "note": "x"}), "note"),  # 多键
    (json.dumps({k: v for k, v in GOOD.items() if k != "date"}), "date"),  # 少键
    (json.dumps({**GOOD, "amount": "7.003.92"}), "amount"),  # 值解析不了
])
def test_validate_rejects(text, err_part):
    fields, _, error = validate(text)
    assert fields is None and err_part in error


def test_validate_normalizes():
    fields, _, error = validate(json.dumps(GOOD, ensure_ascii=False))
    assert error is None and fields == GOOD_NORM


class FakeClient:
    def __init__(self, replies: list[str]):
        self.replies, self.calls = replies, []

    def chat(self, messages):
        self.calls.append([dict(m) for m in messages])
        return LLMResponse(self.replies[len(self.calls) - 1], 1.0, 100, 10, 0, "fake")


@pytest.fixture
def make(monkeypatch):
    monkeypatch.setattr(ocr_llm, "ocr", lambda path, unwarp: OcrResult([], 0.0, 20.0, {}))

    def _make(replies):
        client = FakeClient(replies)
        return OcrLlmExtractor(client=client), client
    return _make


def test_retry_once_then_success(make):
    b, client = make(["oops", json.dumps(GOOD, ensure_ascii=False)])
    r = b.extract("x.png")
    assert r.fields == GOOD_NORM and r.retries == 1 and not r.format_failed
    # 重试时把模型上次的输出和错误原因发回去
    assert client.calls[1][-2] == {"role": "assistant", "content": "oops"}
    assert "JSON" in client.calls[1][-1]["content"]
    assert (r.tokens_in, r.tokens_out, r.latency_s) == (200, 20, 22.0)


def test_degrade_keeps_good_fields(make):
    bad = json.dumps({**GOOD, "amount": "7.003.92"}, ensure_ascii=False)
    b, client = make([bad, bad])
    r = b.extract("x.png")
    assert len(client.calls) == 2  # 只重试一次
    assert r.format_failed and r.fields == {**GOOD_NORM, "amount": None}
    assert set(r.field_errors) == {"amount"}


def test_unparsable_twice_gives_all_null(make):
    b, _ = make(["oops", "oops"])
    r = b.extract("x.png")
    assert r.format_failed and set(r.fields.values()) == {None}
