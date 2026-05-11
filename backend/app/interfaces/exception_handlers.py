"""FastAPI グローバル例外ハンドラ。

HTTPException / RequestValidationError / 未補足 Exception の 3 種を
{ "code": str, "message": str } 形式のエンベロープに正規化する。

PHI ルール §3:
  - リクエストボディ由来の値はそのままログに書かない。
  - 5xx ハンドラではボディをスクラブし、パスのみを error レベルで記録する。
  - エラーメッセージに MRN・氏名・臨床叙述など PHI は含めない。
"""

from __future__ import annotations

import logging
import traceback

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.phi import mask_phi

from .schemas import ErrorResponse

logger = logging.getLogger(__name__)


def _http_code_to_identifier(status_code: int) -> str:
    """HTTP ステータスコードを安定した機械識別子に変換する。

    クライアントが switch/match で判別できるよう小文字スネークケースで返す。
    """
    _MAP: dict[int, str] = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        410: "gone",
        422: "validation_error",
        429: "too_many_requests",
    }
    if status_code in _MAP:
        return _MAP[status_code]
    if 400 <= status_code < 500:
        return "client_error"
    if 500 <= status_code < 600:
        return "server_error"
    return "unknown_error"


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """HTTPException を正規化エンベロープに変換する。

    exc.detail が文字列以外の場合は型名のみを `message` に使い、
    PHI が detail に混入する経路を遮断する。
    """
    if isinstance(exc.detail, str):
        # detail 文字列は開発者が書いた固定テキストを想定するが、
        # PHI 混入を防ぐため mask_phi を通す
        safe_message = mask_phi(exc.detail) if len(exc.detail) > 64 else exc.detail
    else:
        # オブジェクトや dict が渡された場合は型名だけ返す
        safe_message = f"HTTP {exc.status_code}"

    body = ErrorResponse(
        code=_http_code_to_identifier(exc.status_code),
        message=safe_message,
    )
    logger.warning(
        "HTTP %s at %s: %s",
        exc.status_code,
        request.url.path,
        safe_message,
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """RequestValidationError (422) を正規化エンベロープに変換する。

    バリデーションエラーの loc/msg はフィールド名と型不整合を含む可能性があるが
    PHI 値そのものは含まないため、フィールドパスのみを安全に返す。
    ただしボディ値 (input) は絶対にメッセージに含めない。
    """
    # フィールドパスのみを収集し、値 (input) は捨てる
    field_paths = [" -> ".join(str(loc) for loc in err["loc"]) for err in exc.errors()]
    field_summary = "; ".join(field_paths[:5])  # 最大 5 フィールドまで
    if len(field_paths) > 5:
        field_summary += f" (and {len(field_paths) - 5} more)"

    body = ErrorResponse(
        code="validation_error",
        message=f"Request validation failed: {field_summary}",
    )
    logger.warning(
        "Validation error at %s: fields=[%s]",
        request.url.path,
        field_summary,
    )
    return JSONResponse(status_code=422, content=body.model_dump())


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """未補足例外 (500) を正規化エンベロープに変換する。

    スタックトレースは error レベルでログに残すが、
    リクエストパスのみを含め、ボディはスクラブする。
    レスポンスには内部詳細を一切含めない。
    """
    # スタックトレースをログに記録 (ボディなし、パスのみ)
    tb = traceback.format_exc()
    logger.error(
        "Unhandled exception at %s:\n%s",
        request.url.path,
        tb,
    )

    body = ErrorResponse(
        code="internal_error",
        message="An internal server error occurred.",
    )
    return JSONResponse(status_code=500, content=body.model_dump())
