"""臨床医識別 FastAPI 依存関数 (PoC ヘッダー信頼方式)。

X-Clinician-Id ヘッダーから UUID を取り出し、呼び出し元ルーターに返す。
認証プロバイダー・署名検証・セッション管理はスコープ外 (SPEC.md#authentication-poc)。

レイヤー規則:
  - このモジュールは interfaces 層にのみ属する。
  - app.usecases / app.infrastructure を一切インポートしない。
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Header, HTTPException


def get_current_clinician(
    x_clinician_id: str | None = Header(default=None, alias="X-Clinician-Id"),
) -> UUID:
    """X-Clinician-Id ヘッダーから臨床医 UUID を取り出す依存関数。

    ヘッダーが存在しない、または正常な UUID として解析できない場合は
    PHI を含まない 401 エラーエンベロープを返す。
    生のヘッダー値はエラーメッセージに含めない (SPEC.md#authentication-poc)。
    """
    if x_clinician_id is None:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "unauthenticated",
                "message": "Clinician identification required.",
            },
        )
    try:
        return UUID(x_clinician_id)
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "unauthenticated",
                "message": "Clinician identification required.",
            },
        ) from None
