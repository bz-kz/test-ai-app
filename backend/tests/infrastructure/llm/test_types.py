"""mask_phi と Chunk / GenerateResponse の型テスト。"""

from __future__ import annotations

import pytest

from app.infrastructure.llm.types import Chunk, GenerateParams, GenerateResponse, mask_phi


def test_mask_phi_empty_string() -> None:
    assert mask_phi("") == ""


def test_mask_phi_short_string() -> None:
    result = mask_phi("hello")
    # 8文字以下は全文が preview になり masked 0 chars になる
    assert result.startswith("hello")
    assert "masked 0 chars" in result


def test_mask_phi_medium_string() -> None:
    # 8文字を超えたとき、残りがマスクされることを確認する
    value = "some prompt text here"
    result = mask_phi(value)
    assert result.startswith("some pro")
    assert "some prompt text here" not in result
    assert "masked" in result


def test_mask_phi_long_string() -> None:
    long = "a" * 100
    result = mask_phi(long)
    assert result.startswith("a" * 8)
    assert "masked 92 chars" in result
    # 元の文字列がそのまま含まれないことを確認
    assert long not in result


def test_chunk_fields() -> None:
    c = Chunk(text="hello", done=False)
    assert c.text == "hello"
    assert c.done is False
    assert c.confidence is None


def test_chunk_with_confidence() -> None:
    c = Chunk(text="x", done=True, confidence=0.9)
    assert c.confidence == pytest.approx(0.9)


def test_generate_response_fields() -> None:
    r = GenerateResponse(text="output")
    assert r.text == "output"
    assert r.confidence is None


def test_generate_params_defaults() -> None:
    p = GenerateParams()
    assert p.temperature == pytest.approx(0.7)
    assert p.max_tokens == 1500
    assert p.extra == {}
