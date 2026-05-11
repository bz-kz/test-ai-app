"""共通テストフィクスチャ — 認証ヘッダーヘルパー。

BE-012: 全ルーターテストが X-Clinician-Id ヘッダー付きリクエストを送れるよう
固定の臨床医 UUID とヘルパーを提供する。
"""

from __future__ import annotations

from uuid import UUID

import pytest

# テスト用固定臨床医 UUID (本番では実際の UUID に置き換える)
TEST_CLINICIAN_ID = UUID("00000000-0000-0000-0000-0000000a11ce")
TEST_CLINICIAN_ID_STR = str(TEST_CLINICIAN_ID)


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    """X-Clinician-Id ヘッダーを含む dict を返す。TestClient の headers= に渡す。"""
    return {"X-Clinician-Id": TEST_CLINICIAN_ID_STR}


def make_auth_headers(clinician_id: UUID | str | None = None) -> dict[str, str]:
    """任意の臨床医 UUID を使ったヘッダー dict を返すヘルパー関数。

    clinician_id が None の場合はデフォルトの TEST_CLINICIAN_ID を使用する。
    """
    cid = str(clinician_id) if clinician_id is not None else TEST_CLINICIAN_ID_STR
    return {"X-Clinician-Id": cid}
