"""Server-Sent Events (SSE) フレームエンコーダ。

drafts ストリーミング (BE-008) と transcribe ストリーミング (BE-017) が
同じ SSE フォーマット (`data:` / `event:` / `\\n\\n` 区切り) を吐くため、
バイト整形をここに集約する。

PHI 規則:
  - `payload` に渡す dict は呼び出し元が PHI を含むかどうか判断済みであることが前提。
  - エラーフレームの payload には PHI を含めない (ルート側で code / chunk_index のみ
    詰める運用)。

レイヤー方向:
  interfaces 内のユーティリティ。usecases / infrastructure には呼ばれない。
"""

from __future__ import annotations

import json
from typing import Any


def _encode_payload(payload: dict[str, Any] | str) -> str:
    """payload を SSE `data:` 行の値部にエンコードする。

    str ならそのまま (既に JSON 文字列化済みの呼び出し元向け)、
    dict なら `json.dumps(ensure_ascii=False)` でエンコードする。
    """
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False)


def sse_data_frame(payload: dict[str, Any] | str) -> bytes:
    """SSE の通常チャンクフレームを bytes で返す。

    フォーマット: `data: <json>\\n\\n`
    """
    return f"data: {_encode_payload(payload)}\n\n".encode()


def sse_event_frame(name: str, payload: dict[str, Any] | str) -> bytes:
    """SSE の名前付きイベントフレームを bytes で返す。

    フォーマット: `event: <name>\\ndata: <json>\\n\\n`
    `complete` / `error` などの名前を渡す。
    """
    return f"event: {name}\ndata: {_encode_payload(payload)}\n\n".encode()
