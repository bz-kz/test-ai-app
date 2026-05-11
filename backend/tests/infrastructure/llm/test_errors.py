"""InferenceError のマスク要件テスト。raw_prompt が外部に漏れないことを検証する。"""

from __future__ import annotations

from app.infrastructure.llm.errors import InferenceError


def test_inference_error_str_does_not_contain_raw_prompt() -> None:
    """__str__ に raw_prompt が含まれないことを確認する。"""
    raw = "Patient John Doe, MRN 12345 — please draft a record."
    err = InferenceError("generate failed", raw_prompt=raw, status_code=500)
    assert raw not in str(err)


def test_inference_error_repr_does_not_contain_raw_prompt() -> None:
    """__repr__ に raw_prompt が含まれないことを確認する。"""
    raw = "Patient Jane Smith, MRN 99999 — clinical note."
    err = InferenceError("stream failed", raw_prompt=raw)
    assert raw not in repr(err)


def test_inference_error_masked_context_present() -> None:
    """masked_context が設定されていることを確認する。"""
    err = InferenceError("timeout", raw_prompt="some prompt text")
    assert err.masked_context
    assert "timeout" in err.masked_context


def test_inference_error_no_prompt() -> None:
    """raw_prompt なしでも動作することを確認する。"""
    err = InferenceError("connection refused")
    assert str(err)
    assert "no prompt" in str(err)


def test_inference_error_status_code() -> None:
    err = InferenceError("non-200", raw_prompt="x", status_code=503)
    assert err.status_code == 503
    assert "503" in repr(err)
