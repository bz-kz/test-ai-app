"""app/domain/phi.py のユニットテスト (BE-010 / BE-015)。

mask_phi の既存テストと short_id の新規テストを収録する。
BE-015 Item 1: 4 文字以下の短い値が "***" を返すことを追加検証する。
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

    def test_five_char_string_returns_preview(self) -> None:
        """5 文字は閾値 (4 文字) を超えるため、先頭 5 文字 + masked 0 chars を返す。"""
        result = mask_phi("hello")
        assert result == "hello...[masked 0 chars]"

    def test_long_string_preview_8_chars(self) -> None:
        value = "abcdefghijklmno"
        result = mask_phi(value)
        assert result.startswith("abcdefgh")
        assert "masked 7 chars" in result

    def test_exactly_8_chars_no_masked_suffix(self) -> None:
        result = mask_phi("12345678")
        assert result == "12345678...[masked 0 chars]"

    # -----------------------------------------------------------------------
    # BE-015 Item 1 — 短い値のマスク動作
    # -----------------------------------------------------------------------

    def test_empty_string_returns_empty_be015(self) -> None:
        """空文字列は既存と同じく空文字列を返す。"""
        assert mask_phi("") == ""

    def test_one_char_value_returns_stars(self) -> None:
        """1 文字は ≤4 文字閾値に該当するため '***' を返す。"""
        assert mask_phi("A") == "***"

    def test_four_char_value_returns_stars(self) -> None:
        """4 文字は閾値ちょうどのため '***' を返す。値が全公開されない。"""
        result = mask_phi("1234")
        assert result == "***"
        # 元の値が一切含まれない
        assert "1234" not in result

    def test_five_char_value_returns_preview_not_stars(self) -> None:
        """5 文字は閾値を超えるため '***' ではなくプレビュー形式を返す。"""
        result = mask_phi("12345")
        assert result != "***"
        assert "[masked" in result

    def test_nine_char_value_masks_tail(self) -> None:
        """9 文字: 先頭 8 文字を保持し残り 1 文字をマスクする。"""
        result = mask_phi("abcdefghi")
        assert result == "abcdefgh...[masked 1 chars]"
        # 9 文字目 'i' はレスポンスに含まれない
        assert result.endswith("...[masked 1 chars]")


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
