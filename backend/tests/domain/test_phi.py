"""app/domain/phi.py のユニットテスト (BE-010)。

mask_phi の既存テストと short_id の新規テストを収録する。
"""

from __future__ import annotations

from uuid import UUID

import pytest

from app.domain.phi import mask_phi, short_id

# ---------------------------------------------------------------------------
# mask_phi
# ---------------------------------------------------------------------------


class TestMaskPhi:
    def test_empty_string_returns_empty(self) -> None:
        assert mask_phi("") == ""

    def test_short_string_masked_beyond_8_chars(self) -> None:
        result = mask_phi("hello")
        # 5 文字 → 先頭 5 文字 + masked 0 chars
        assert result == "hello...[masked 0 chars]"

    def test_long_string_preview_8_chars(self) -> None:
        value = "abcdefghijklmno"
        result = mask_phi(value)
        assert result.startswith("abcdefgh")
        assert "masked 7 chars" in result

    def test_exactly_8_chars_no_masked_suffix(self) -> None:
        result = mask_phi("12345678")
        assert result == "12345678...[masked 0 chars]"


# ---------------------------------------------------------------------------
# short_id (BE-010 Item 3)
# ---------------------------------------------------------------------------


class TestShortId:
    def test_typical_uuid_returns_8_hex_plus_ellipsis(self) -> None:
        """標準的な UUID v4 → ハイフン除去後の先頭 8 桁 + '…'"""
        uid = UUID("550e8400-e29b-41d4-a716-446655440000")
        result = short_id(uid)
        # ハイフン除去: 550e8400e29b41d4a716446655440000
        assert result == "550e8400…"

    def test_uuid_string_same_as_uuid_object(self) -> None:
        """文字列と UUID オブジェクトで同じ結果になる。"""
        uid_str = "550e8400-e29b-41d4-a716-446655440000"
        uid_obj = UUID(uid_str)
        assert short_id(uid_str) == short_id(uid_obj)

    def test_all_zeros_uuid(self) -> None:
        uid = UUID("00000000-0000-0000-0000-000000000000")
        result = short_id(uid)
        assert result == "00000000…"

    def test_empty_string_returns_ellipsis(self) -> None:
        """空文字列はハイフン除去後も空 → '…' のみ返す。"""
        result = short_id("")
        assert result == "…"

    def test_non_uuid_string_returns_first_8_chars(self) -> None:
        """UUID 形式でない文字列も先頭 8 文字 + '…' を返す。"""
        result = short_id("abcdefghXXXX")
        assert result == "abcdefgh…"

    def test_short_non_uuid_string(self) -> None:
        """8 文字未満の非 UUID 文字列 → そのまま + '…'。"""
        result = short_id("abc")
        assert result == "abc…"

    def test_result_never_contains_full_uuid(self) -> None:
        """返却値がフル UUID を含まないこと (再識別困難性の確認)。"""
        uid = UUID("f47ac10b-58cc-4372-a567-0e02b2c3d479")
        result = short_id(uid)
        assert "f47ac10b-58cc-4372-a567-0e02b2c3d479" not in result
        assert len(result) < 20  # 8 桁 + '…' なので必ず短い

    @pytest.mark.parametrize(
        "value",
        [
            UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "aaaaaaaabbbbccccddddeeeeeeeeeeee",
        ],
    )
    def test_parametrized_uuid_variants(self, value: object) -> None:
        result = short_id(value)
        assert result == "aaaaaaaa…"
