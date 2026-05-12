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

# traceback モジュールはスタックフレーム情報の抽出にのみ使用する。
# format_exc() は 5xx ハンドラでは使わない — ローカル変数に PHI が含まれうるため。
import traceback
from typing import cast

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.phi import mask_phi
from app.usecases.errors import InferenceError

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

    exc.detail が {"code": str, "message": str} 形式の dict の場合は
    そのまま使用する (機能エンドポイントが特定の code を返すために使う)。
    文字列の場合は PHI 混入を防ぐため mask_phi を通す。
    それ以外の型の場合はステータスコードのみを返す。
    """
    detail: object = exc.detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        # 機能エンドポイントが明示的に渡した PHI-safe なエンベロープをそのまま使う
        _d = cast(dict[str, object], detail)
        safe_code = str(_d["code"])
        safe_message = str(_d["message"])
    elif isinstance(detail, str):
        # 開発者が書いた短い detail 文字列でも PHI が紛れ込む可能性がある
        # (例: f"patient {mrn} not found")。長さに関わらず無条件にマスクする。
        safe_code = _http_code_to_identifier(exc.status_code)
        safe_message = mask_phi(detail)
    else:
        # オブジェクトや dict が渡された場合は型名だけ返す
        safe_code = _http_code_to_identifier(exc.status_code)
        safe_message = f"HTTP {exc.status_code}"

    body = ErrorResponse(
        code=safe_code,
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


async def inference_error_handler(
    request: Request,
    exc: InferenceError,
) -> JSONResponse:
    """InferenceError (LLM 呼び出し失敗) を 503 に変換する。

    exc.masked_context には PHI マスク済みのコンテキストが含まれる (BE-001 実装)。
    プロンプト原文は __str__ にも含まれないため、そのまま WARNING ログに出力できる。
    レスポンスボディには PHI・プロンプト内容を一切含めない。
    """
    # masked_context は BE-001 の InferenceError が生成するマスク済み文字列
    logger.warning(
        "InferenceError at %s: %s",
        request.url.path,
        exc.masked_context,
    )
    body = ErrorResponse(
        code="inference_unavailable",
        message="Inference service is temporarily unavailable.",
    )
    return JSONResponse(status_code=503, content=body.model_dump())


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """未補足例外 (500) を正規化エンベロープに変換する。

    スタックトレースは error レベルでログに残すが、
    リクエストパスのみを含め、ボディはスクラブする。
    レスポンスには内部詳細を一切含めない。
    """
    # ローカル変数にPHI(患者情報など)が含まれうるため、フルトレースバックは記録しない。
    # 例外クラス名 + 発生ファイル/行番号のみを記録する (デバッグ相関に十分)。
    tb_frames = traceback.extract_tb(exc.__traceback__)
    if tb_frames:
        top_frame = tb_frames[-1]
        # コンテナ内の絶対パス (/app/app/usecases/...) からプロジェクト相対パス
        # (app/usecases/...) に正規化する。実装構造の漏洩を最小化するため。
        rel_filename = top_frame.filename.removeprefix("/app/")
        location = f"{rel_filename}:{top_frame.lineno}"
    else:
        location = "<unknown>"
    exc_class = f"{exc.__class__.__module__}.{exc.__class__.__name__}"
    logger.error(
        "Unhandled exception at %s: %s at %s",
        request.url.path,
        exc_class,
        location,
    )

    body = ErrorResponse(
        code="internal_error",
        message="An internal server error occurred.",
    )
    return JSONResponse(status_code=500, content=body.model_dump())
