"""PhiLoggingFilter のユニットテスト。"""

from __future__ import annotations

import logging

from app.infrastructure.db.logging_filter import PhiLoggingFilter, get_phi_column_names


def _make_record(msg: str) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None,
    )
    return record


def test_phi_filter_allows_non_phi_message() -> None:
    """PHI カラム名を含まないログは通過する。"""
    f = PhiLoggingFilter()
    record = _make_record("encounter added: id=abc")
    result = f.filter(record)
    assert result is True
    # メッセージが変更されないことを確認する
    assert "encounter added" in record.msg


def test_phi_filter_masks_phi_column_name_in_message() -> None:
    """PHI カラム名 (mrn) を含むメッセージがマスクされることを確認する。"""
    f = PhiLoggingFilter()
    record = _make_record("patient lookup: mrn=MRN001 found")
    f.filter(record)
    # マスクされた後は元の PHI 値が含まれないこと
    assert "MRN001" not in record.msg
    assert "phi" in record.msg.lower() or "masked" in record.msg.lower()


def test_phi_column_names_is_frozenset() -> None:
    """get_phi_column_names() が frozenset を返すことを確認する。"""
    names = get_phi_column_names()
    assert isinstance(names, frozenset)
    assert len(names) > 0
