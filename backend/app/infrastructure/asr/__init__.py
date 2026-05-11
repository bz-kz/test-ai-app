"""ASR インフラ層の公開 API。

外部から使用するシンボル:
- LocalASRClient          : プロトコル（型注釈・isinstance チェック用）
- WhisperCppLocalASRClient: 本番用具体実装
- AudioPayload            : transcribe() に渡す音声データ型
- TranscribeParams        : transcribe() パラメータ
- TranscribeResponse      : transcribe() の戻り値
- ASRError                : ASR 呼び出し失敗時の例外
- ASR_BASE_URL            : 設定値
- ASR_MODEL               : 設定値
- ASR_TIMEOUT_S           : 設定値

FakeLocalASRClient はテストコードのみ直接インポートすること。
"""

from .client import LocalASRClient
from .config import ASR_BASE_URL, ASR_MODEL, ASR_TIMEOUT_S
from .errors import ASRError
from .types import AudioPayload, TranscribeParams, TranscribeResponse
from .whisper_cpp_client import WhisperCppLocalASRClient

__all__ = [
    "LocalASRClient",
    "WhisperCppLocalASRClient",
    "AudioPayload",
    "TranscribeParams",
    "TranscribeResponse",
    "ASRError",
    "ASR_BASE_URL",
    "ASR_MODEL",
    "ASR_TIMEOUT_S",
    "make_asr_client",
]


def make_asr_client() -> LocalASRClient:
    """本番用 ASR クライアントを生成して返す。

    usecases/di.py がシングルトンキャッシュ管理のためにこのファクトリを呼び出す。
    具体実装 (WhisperCppLocalASRClient) の名前を usecases 層に露出させない。
    """
    return WhisperCppLocalASRClient()
