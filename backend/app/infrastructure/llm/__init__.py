"""LLM インフラ層の公開 API。

外部から使用するシンボル:
- LocalLLMClient   : プロトコル（型注釈・isinstance チェック用）
- OllamaLocalLLMClient : 本番用具体実装
- GenerateParams   : 推論パラメータ
- GenerateResponse : generate() の戻り値
- Chunk            : stream() が yield する型
- InferenceError   : LLM 呼び出し失敗時の例外
- mask_phi         : PHI マスクユーティリティ

FakeLocalLLMClient はテストコードのみ直接インポートすること。
"""

from .client import LocalLLMClient
from .config import LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT_S
from .errors import InferenceError
from .ollama_client import OllamaLocalLLMClient
from .types import Chunk, GenerateParams, GenerateResponse, mask_phi

__all__ = [
    "LocalLLMClient",
    "OllamaLocalLLMClient",
    "GenerateParams",
    "GenerateResponse",
    "Chunk",
    "InferenceError",
    "mask_phi",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_TIMEOUT_S",
]
