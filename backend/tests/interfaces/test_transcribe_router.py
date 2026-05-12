"""音声文字起こしエンドポイントのルーターテスト (BE-014 / BE-017)。

TestClient + インメモリ SQLite + FakeLocalASRClient を使い、
Postgres・ASR サービスなしで実行できる。

BE-014 Acceptance:
  (a) POST /encounters/{id}/transcribe 200 — 正常文字起こし
  (b) 存在しない encounter_id → 404 code="encounter_not_found" (UUID 非エコー)
  (c) X-Clinician-Id ヘッダーなし → 401 code="unauthenticated"
  (d) ペイロードが 2MB 超 → 422 code="audio_too_large"
  (e) サポート外コンテンツタイプ → 415 code="unsupported_media_type"
  (f) ASR が ASRError (非タイムアウト) → 503 code="transcription_unavailable"
  (g) ASR が ASRError (タイムアウト) → 504 code="transcription_timeout"
  (h) エラーレスポンスに PHI (音声内容・トランスクリプト) が含まれない
  (i) 監査ログ行数が増えない (DB 書き込みなし)

BE-017 Acceptance (SSE ストリーミング):
  (f) 200 SSE ハッピーパス — data: フレームと event: complete フレームを確認
  (g) 401 ヘッダーなし — ストリーム開始前の同期エラー
  (h) 404 存在しない encounter — ストリーム開始前の同期エラー
  (i) 415 サポート外コンテンツタイプ
  (j) 422 ペイロード過大
  (k) mid-stream transcription_unavailable SSE error フレーム
  (l) mid-stream transcription_timeout SSE error フレーム
  (m) SSE error フレームに masked_context や音声長が含まれない (PHI ルール)
  (n) X-Accel-Buffering: no ヘッダーが存在する
"""

from __future__ import annotations

import io
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.entities import Encounter, Patient
from app.infrastructure.asr.fake_client import FakeLocalASRClient
from app.infrastructure.asr.types import (
    AudioPayload,
    TranscribeChunk,
    TranscribeParams,
    TranscribeResponse,
)
from app.infrastructure.db.engine import Base
from app.infrastructure.db.models import AuditLogORM
from app.infrastructure.db.repositories import (
    EncounterRepository,
    PatientRepository,
)
from app.interfaces.auth import get_current_clinician
from app.interfaces.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
    unhandled_exception_handler,
)
from app.interfaces.routers.transcribe import router as transcribe_router
from app.usecases.di import (
    get_asr_client,
    make_stream_transcribe_audio,
    make_transcribe_audio,
)
from app.usecases.transcribe import transcribe_audio
from app.usecases.transcribe_stream import stream_transcribe_audio
from tests.conftest import TEST_CLINICIAN_ID

# ---------------------------------------------------------------------------
# テスト用アプリとインメモリ DB のセットアップ
# ---------------------------------------------------------------------------


def _make_test_app(session: AsyncSession, asr: FakeLocalASRClient) -> FastAPI:
    """インメモリ DB セッションと FakeASR を DI に差し込んだテスト用 FastAPI を生成する。"""

    def _override_make_transcribe_audio():  # type: ignore[no-untyped-def]
        encounter_repo = EncounterRepository(session)

        async def _transcribe(
            audio: AudioPayload,
            params: TranscribeParams | None,
            encounter_id: UUID,
            clinician_id: UUID,
        ) -> TranscribeResponse:
            return await transcribe_audio(
                audio=audio,
                params=params,
                encounter_id=encounter_id,
                clinician_id=clinician_id,
                asr=asr,
                encounter_repo=encounter_repo,
            )

        return _transcribe

    def _override_make_stream_transcribe_audio():  # type: ignore[no-untyped-def]
        encounter_repo = EncounterRepository(session)

        async def _stream(
            audio: AudioPayload,
            params: TranscribeParams | None,
            encounter_id: UUID,
            clinician_id: UUID,
        ) -> AsyncGenerator[TranscribeChunk, None]:
            async for chunk in await stream_transcribe_audio(
                audio=audio,
                params=params,
                encounter_id=encounter_id,
                clinician_id=clinician_id,
                asr=asr,
                encounter_repo=encounter_repo,
            ):
                yield chunk

        return _stream

    test_app = FastAPI()
    test_app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    test_app.add_exception_handler(
        RequestValidationError,
        request_validation_exception_handler,  # type: ignore[arg-type]
    )
    test_app.add_exception_handler(Exception, unhandled_exception_handler)
    test_app.include_router(transcribe_router, prefix="")

    # DI オーバーライド
    test_app.dependency_overrides[make_transcribe_audio] = _override_make_transcribe_audio
    test_app.dependency_overrides[make_stream_transcribe_audio] = (
        _override_make_stream_transcribe_audio
    )
    test_app.dependency_overrides[get_asr_client] = lambda: asr
    # BE-012: テスト用固定臨床医 UUID を返すように auth 依存を上書きする
    test_app.dependency_overrides[get_current_clinician] = lambda: TEST_CLINICIAN_ID

    return test_app


@pytest.fixture()
async def session() -> AsyncGenerator[AsyncSession, None]:
    """インメモリ SQLite セッション。各テストで独立した DB を使う。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture()
def fake_asr() -> FakeLocalASRClient:
    return FakeLocalASRClient()


@pytest.fixture()
def client(session: AsyncSession, fake_asr: FakeLocalASRClient) -> TestClient:
    app = _make_test_app(session, fake_asr)
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# ヘルパー: 患者と受診を作成する
# ---------------------------------------------------------------------------


async def _create_encounter(session: AsyncSession) -> Encounter:
    """テスト用の患者 + 受診を DB に作成して受診を返す。"""
    patient = Patient(
        id=uuid4(),
        mrn="T-001",
        family_name="テスト",
        given_name="患者",
        date_of_birth=datetime(1990, 1, 1, tzinfo=UTC),
        created_at=datetime.now(tz=UTC),
    )
    encounter = Encounter(
        id=uuid4(),
        patient_id=patient.id,
        encountered_at=datetime.now(tz=UTC),
        clinician_id=TEST_CLINICIAN_ID,
        created_at=datetime.now(tz=UTC),
    )
    patient_repo = PatientRepository(session)
    encounter_repo = EncounterRepository(session)
    await patient_repo.add(patient)
    await encounter_repo.add(encounter)
    await session.flush()
    return encounter


def _audio_file(content: bytes = b"fake-audio") -> dict:
    """multipart files dict を返す。"""
    return {"audio": ("audio.webm", io.BytesIO(content), "audio/webm;codecs=opus")}


AUTH_HEADERS = {"X-Clinician-Id": str(TEST_CLINICIAN_ID)}


# ---------------------------------------------------------------------------
# テストケース
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transcribe_happy_path(session: AsyncSession, fake_asr: FakeLocalASRClient) -> None:
    """正常系: 受診が存在し ASR が成功する場合に 200 とトランスクリプトを返す。"""
    encounter = await _create_encounter(session)
    app = _make_test_app(session, fake_asr)

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post(
            f"/encounters/{encounter.id}/transcribe",
            files=_audio_file(),
            headers=AUTH_HEADERS,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["text"] == FakeLocalASRClient.DEFAULT_TRANSCRIPT
    assert data["encounter_id"] == str(encounter.id)
    assert data["duration_seconds"] is None


@pytest.mark.asyncio
async def test_transcribe_missing_auth_header(
    session: AsyncSession, fake_asr: FakeLocalASRClient
) -> None:
    """X-Clinician-Id ヘッダーがない場合は 401 を返す。"""
    encounter = await _create_encounter(session)
    app = _make_test_app(session, fake_asr)
    # 認証 override を外して実際の依存関数を使う
    app.dependency_overrides.pop(get_current_clinician, None)

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post(
            f"/encounters/{encounter.id}/transcribe",
            files=_audio_file(),
            # ヘッダーなし
        )

    assert resp.status_code == 401
    data = resp.json()
    assert data["code"] == "unauthenticated"


@pytest.mark.asyncio
async def test_transcribe_encounter_not_found(
    session: AsyncSession, fake_asr: FakeLocalASRClient
) -> None:
    """受診が存在しない場合は 404 を返す。UUID はエラーメッセージに含まれない。"""
    unknown_id = uuid4()
    app = _make_test_app(session, fake_asr)

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post(
            f"/encounters/{unknown_id}/transcribe",
            files=_audio_file(),
            headers=AUTH_HEADERS,
        )

    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "encounter_not_found"
    assert str(unknown_id) not in data["message"]


@pytest.mark.asyncio
async def test_transcribe_audio_too_large(
    session: AsyncSession, fake_asr: FakeLocalASRClient
) -> None:
    """2MB 超のペイロードは 422 を返す。"""
    encounter = await _create_encounter(session)
    app = _make_test_app(session, fake_asr)
    large_audio = b"x" * (2 * 1024 * 1024 + 1)

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post(
            f"/encounters/{encounter.id}/transcribe",
            files={"audio": ("big.webm", io.BytesIO(large_audio), "audio/webm;codecs=opus")},
            headers=AUTH_HEADERS,
        )

    assert resp.status_code == 422
    data = resp.json()
    assert data["code"] == "audio_too_large"


@pytest.mark.asyncio
async def test_transcribe_unsupported_content_type(
    session: AsyncSession, fake_asr: FakeLocalASRClient
) -> None:
    """サポート外コンテンツタイプは 415 を返す。"""
    encounter = await _create_encounter(session)
    app = _make_test_app(session, fake_asr)

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post(
            f"/encounters/{encounter.id}/transcribe",
            files={"audio": ("audio.mp3", io.BytesIO(b"mp3data"), "audio/mpeg")},
            headers=AUTH_HEADERS,
        )

    assert resp.status_code == 415
    data = resp.json()
    assert data["code"] == "unsupported_media_type"


@pytest.mark.asyncio
async def test_transcribe_asr_unavailable(session: AsyncSession) -> None:
    """ASR が非タイムアウトエラーのとき 503 を返す。"""
    encounter = await _create_encounter(session)
    error_asr = FakeLocalASRClient(force_error=True)
    app = _make_test_app(session, error_asr)

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post(
            f"/encounters/{encounter.id}/transcribe",
            files=_audio_file(),
            headers=AUTH_HEADERS,
        )

    assert resp.status_code == 503
    data = resp.json()
    assert data["code"] == "transcription_unavailable"
    # PHI がエラーレスポンスに含まれないことを確認
    assert "fake-audio" not in data["message"]
    assert FakeLocalASRClient.DEFAULT_TRANSCRIPT not in data["message"]


@pytest.mark.asyncio
async def test_transcribe_asr_timeout(session: AsyncSession) -> None:
    """ASR がタイムアウトエラーのとき 504 を返す。"""
    encounter = await _create_encounter(session)
    timeout_asr = FakeLocalASRClient(force_timeout=True)
    app = _make_test_app(session, timeout_asr)

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post(
            f"/encounters/{encounter.id}/transcribe",
            files=_audio_file(),
            headers=AUTH_HEADERS,
        )

    assert resp.status_code == 504
    data = resp.json()
    assert data["code"] == "transcription_timeout"


@pytest.mark.asyncio
async def test_transcribe_no_phi_in_error_responses(session: AsyncSession) -> None:
    """全エラーレスポンスに PHI が含まれないことを確認する。"""
    encounter = await _create_encounter(session)

    # 503 エラー
    error_asr = FakeLocalASRClient(force_error=True)
    error_app = _make_test_app(session, error_asr)

    with TestClient(error_app, raise_server_exceptions=False) as c:
        resp = c.post(
            f"/encounters/{encounter.id}/transcribe",
            files=_audio_file(b"patient-audio-data"),
            headers=AUTH_HEADERS,
        )

    assert resp.status_code == 503
    response_str = resp.text
    # 音声バイト列の内容がレスポンスに漏れていないことを確認
    assert "patient-audio-data" not in response_str
    assert str(encounter.id) not in response_str


@pytest.mark.asyncio
async def test_transcribe_no_audit_log_row(session: AsyncSession) -> None:
    """文字起こし成功後も監査ログ行が追加されないことを確認する (DB 書き込みなし)。"""
    encounter = await _create_encounter(session)
    asr = FakeLocalASRClient()
    app = _make_test_app(session, asr)

    # 文字起こし前の監査ログ数を確認
    result_before = await session.execute(select(AuditLogORM))
    count_before = len(result_before.scalars().all())

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post(
            f"/encounters/{encounter.id}/transcribe",
            files=_audio_file(),
            headers=AUTH_HEADERS,
        )

    assert resp.status_code == 200

    # 文字起こし後の監査ログ数が変わっていないことを確認
    result_after = await session.execute(select(AuditLogORM))
    count_after = len(result_after.scalars().all())
    assert count_after == count_before


# ---------------------------------------------------------------------------
# BE-017: SSE ストリーミングエンドポイントのテスト
# ---------------------------------------------------------------------------


def _parse_sse_frames(raw: str) -> list[dict]:
    """SSE レスポンスを解析してフレームの list を返す。

    各フレームは {"event": str | None, "data": str} の形式。
    """
    frames: list[dict] = []
    current: dict = {"event": None, "data": None}

    for line in raw.splitlines():
        if line.startswith("event:"):
            current["event"] = line[len("event:") :].strip()
        elif line.startswith("data:"):
            current["data"] = line[len("data:") :].strip()
        elif line == "":
            if current["data"] is not None:
                frames.append(dict(current))
            current = {"event": None, "data": None}

    if current["data"] is not None:
        frames.append(current)

    return frames


@pytest.mark.asyncio
async def test_stream_transcribe_happy_path(session: AsyncSession) -> None:
    """(f) 200 SSE ハッピーパス: data: フレームと event: complete フレームを確認する。"""
    encounter = await _create_encounter(session)
    asr = FakeLocalASRClient(n_chunks=3)
    app = _make_test_app(session, asr)

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post(
            f"/encounters/{encounter.id}/transcribe/stream",
            files=_audio_file(),
            headers=AUTH_HEADERS,
        )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")

    frames = _parse_sse_frames(resp.text)

    # 3 通常チャンクフレーム + 1 完了フレーム
    assert len(frames) == 4

    # 通常チャンクフレームの確認
    for i in range(3):
        assert frames[i]["event"] is None
        data = json.loads(frames[i]["data"])
        assert data["done"] is False
        assert data["chunk_index"] == i
        assert data["chunk_count"] == 3
        assert "text" in data

    # 完了フレームの確認
    assert frames[3]["event"] == "complete"
    done_data = json.loads(frames[3]["data"])
    assert "full_text" in done_data
    assert done_data["chunk_count"] == 3


@pytest.mark.asyncio
async def test_stream_transcribe_x_accel_buffering_header(session: AsyncSession) -> None:
    """(n) X-Accel-Buffering: no ヘッダーが存在することを確認する (BE-013 パリティ)。"""
    encounter = await _create_encounter(session)
    asr = FakeLocalASRClient()
    app = _make_test_app(session, asr)

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post(
            f"/encounters/{encounter.id}/transcribe/stream",
            files=_audio_file(),
            headers=AUTH_HEADERS,
        )

    assert resp.headers.get("x-accel-buffering") == "no"
    assert resp.headers.get("cache-control") == "no-cache"


@pytest.mark.asyncio
async def test_stream_transcribe_missing_auth_header(
    session: AsyncSession, fake_asr: FakeLocalASRClient
) -> None:
    """(g) X-Clinician-Id ヘッダーがない場合は 401 を返す (ストリーム開始前の同期エラー)。"""
    encounter = await _create_encounter(session)
    app = _make_test_app(session, fake_asr)
    # 認証 override を外して実際の依存関数を使う
    app.dependency_overrides.pop(get_current_clinician, None)

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post(
            f"/encounters/{encounter.id}/transcribe/stream",
            files=_audio_file(),
            # ヘッダーなし
        )

    assert resp.status_code == 401
    data = resp.json()
    assert data["code"] == "unauthenticated"


@pytest.mark.asyncio
async def test_stream_transcribe_encounter_not_found(
    session: AsyncSession, fake_asr: FakeLocalASRClient
) -> None:
    """(h) 存在しない encounter_id → 404 (ストリーム開始前の同期エラー)。"""
    unknown_id = uuid4()
    app = _make_test_app(session, fake_asr)

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post(
            f"/encounters/{unknown_id}/transcribe/stream",
            files=_audio_file(),
            headers=AUTH_HEADERS,
        )

    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "encounter_not_found"
    # UUID はエラーメッセージに含まれない
    assert str(unknown_id) not in data["message"]


@pytest.mark.asyncio
async def test_stream_transcribe_unsupported_content_type(
    session: AsyncSession, fake_asr: FakeLocalASRClient
) -> None:
    """(i) サポート外コンテンツタイプは 415 を返す (ストリーム開始前の同期エラー)。"""
    encounter = await _create_encounter(session)
    app = _make_test_app(session, fake_asr)

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post(
            f"/encounters/{encounter.id}/transcribe/stream",
            files={"audio": ("audio.mp3", io.BytesIO(b"mp3data"), "audio/mpeg")},
            headers=AUTH_HEADERS,
        )

    assert resp.status_code == 415
    data = resp.json()
    assert data["code"] == "unsupported_media_type"


@pytest.mark.asyncio
async def test_stream_transcribe_audio_too_large(
    session: AsyncSession, fake_asr: FakeLocalASRClient
) -> None:
    """(j) 2MB 超のペイロードは 422 を返す (ストリーム開始前の同期エラー)。"""
    encounter = await _create_encounter(session)
    app = _make_test_app(session, fake_asr)
    large_audio = b"x" * (2 * 1024 * 1024 + 1)

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post(
            f"/encounters/{encounter.id}/transcribe/stream",
            files={"audio": ("big.webm", io.BytesIO(large_audio), "audio/webm;codecs=opus")},
            headers=AUTH_HEADERS,
        )

    assert resp.status_code == 422
    data = resp.json()
    assert data["code"] == "audio_too_large"


@pytest.mark.asyncio
async def test_stream_transcribe_mid_stream_unavailable(session: AsyncSession) -> None:
    """(k) mid-stream ASRError (非タイムアウト) → SSE event: error フレーム。"""
    encounter = await _create_encounter(session)
    # チャンク 1 でエラーを発生させる
    error_asr = FakeLocalASRClient(force_error_at_chunk=1, n_chunks=3)
    app = _make_test_app(session, error_asr)

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post(
            f"/encounters/{encounter.id}/transcribe/stream",
            files=_audio_file(),
            headers=AUTH_HEADERS,
        )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")

    frames = _parse_sse_frames(resp.text)

    # チャンク 0 は成功するため data: フレームが 1 つ
    # その後 event: error フレームが来る
    assert len(frames) >= 2
    error_frame = frames[-1]
    assert error_frame["event"] == "error"
    error_data = json.loads(error_frame["data"])
    assert error_data["code"] == "transcription_unavailable"
    assert "chunk_index" in error_data


@pytest.mark.asyncio
async def test_stream_transcribe_mid_stream_timeout(session: AsyncSession) -> None:
    """(l) mid-stream ASRError (タイムアウト) → SSE error フレーム code=transcription_timeout。"""
    encounter = await _create_encounter(session)
    # force_total_timeout は最初のチャンクで timeout=True の ASRError を送出する
    timeout_asr = FakeLocalASRClient(force_total_timeout=True)
    app = _make_test_app(session, timeout_asr)

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post(
            f"/encounters/{encounter.id}/transcribe/stream",
            files=_audio_file(),
            headers=AUTH_HEADERS,
        )

    assert resp.status_code == 200

    frames = _parse_sse_frames(resp.text)
    assert len(frames) >= 1
    error_frame = frames[-1]
    assert error_frame["event"] == "error"
    error_data = json.loads(error_frame["data"])
    assert error_data["code"] == "transcription_timeout"


@pytest.mark.asyncio
async def test_stream_transcribe_error_frame_no_phi(session: AsyncSession) -> None:
    """(m) SSE error フレームに masked_context や音声データが含まれない (PHI ルール)。"""
    encounter = await _create_encounter(session)
    error_asr = FakeLocalASRClient(force_error_at_chunk=0)
    app = _make_test_app(session, error_asr)

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post(
            f"/encounters/{encounter.id}/transcribe/stream",
            files=_audio_file(b"patient-audio-phi"),
            headers=AUTH_HEADERS,
        )

    response_text = resp.text
    # masked_context がフレームペイロードに含まれない
    assert "masked_context" not in response_text
    # 音声バイト列が含まれない
    assert "patient-audio-phi" not in response_text
    # encounter UUID が含まれない
    assert str(encounter.id) not in response_text


@pytest.mark.asyncio
async def test_stream_transcribe_no_audit_log_row(session: AsyncSession) -> None:
    """(n2) SSE ストリーミング文字起こし後も監査ログ行が追加されない (DB 書き込みなし)。"""
    encounter = await _create_encounter(session)
    asr = FakeLocalASRClient()
    app = _make_test_app(session, asr)

    result_before = await session.execute(select(AuditLogORM))
    count_before = len(result_before.scalars().all())

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post(
            f"/encounters/{encounter.id}/transcribe/stream",
            files=_audio_file(),
            headers=AUTH_HEADERS,
        )

    assert resp.status_code == 200

    result_after = await session.execute(select(AuditLogORM))
    count_after = len(result_after.scalars().all())
    assert count_after == count_before
