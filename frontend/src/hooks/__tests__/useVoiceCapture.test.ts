import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useVoiceCapture } from "../useVoiceCapture";
import { AUDIO_MAX_DURATION_S, AUDIO_MIME_TYPE } from "@/lib/constants";

// transcribe サービスをモック — 実際の fetch は呼び出さない
vi.mock("@/services/transcribe", () => ({
  transcribeAudio: vi.fn(),
  streamTranscribeAudio: vi.fn(),
}));

// constants モジュールをモック — ASR_STREAMING_ENABLED を各テストで制御する
vi.mock("@/lib/constants", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/constants")>();
  return {
    ...original,
    // デフォルトは false — 既存 FE-009 テストを変更しない
    ASR_STREAMING_ENABLED: false,
  };
});

import { transcribeAudio, streamTranscribeAudio } from "@/services/transcribe";
import * as constants from "@/lib/constants";
const mockTranscribe = vi.mocked(transcribeAudio);
const mockStreamTranscribe = vi.mocked(streamTranscribeAudio);

// ---- MediaRecorder フェイク ----

function makeFakeMediaRecorder(isSupported: boolean) {
  class FakeMediaRecorder {
    state: "inactive" | "recording" = "inactive";
    ondataavailable: ((e: { data: Blob }) => void) | null = null;
    onstop: (() => void) | null = null;

    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    constructor(_stream: MediaStream, _opts?: MediaRecorderOptions) {
      // フェイクインスタンス — 引数は型チェック用のみ
    }

    start() {
      this.state = "recording";
      // データチャンクをシミュレートする
      if (this.ondataavailable) {
        this.ondataavailable({ data: new Blob(["audio"], { type: AUDIO_MIME_TYPE }) });
      }
    }

    stop() {
      this.state = "inactive";
      if (this.onstop) {
        this.onstop();
      }
    }

    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    static isTypeSupported(_mime: string) {
      return isSupported;
    }
  }
  return FakeMediaRecorder;
}

// ---- getUserMedia フェイク ----

function makeFakeStream(tracks: MediaStreamTrack[] = []): MediaStream {
  const defaultTracks =
    tracks.length > 0 ? tracks : [{ stop: vi.fn() } as unknown as MediaStreamTrack];
  return {
    getTracks: () => defaultTracks,
  } as unknown as MediaStream;
}

const FAKE_ENCOUNTER_ID = "00000000-0000-0000-0000-000000000099";

describe("useVoiceCapture", () => {
  beforeEach(() => {
    mockTranscribe.mockReset();
    mockStreamTranscribe.mockReset();
    // デフォルトは非ストリーミングパス
    vi.mocked(constants).ASR_STREAMING_ENABLED = false;

    // デフォルト: コーデックサポートあり
    vi.stubGlobal("MediaRecorder", makeFakeMediaRecorder(true));

    // デフォルト: getUserMedia 成功
    const fakeStream = makeFakeStream();
    Object.defineProperty(global.navigator, "mediaDevices", {
      value: { getUserMedia: vi.fn().mockResolvedValue(fakeStream) },
      configurable: true,
      writable: true,
    });
  });

  afterEach(() => {
    // フェイクタイマーを使うテストがタイムアウトした場合でも必ずリアルタイマーに戻す
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("初期状態は idle、elapsedMs=0、transcript=''、error=null", () => {
    const { result } = renderHook(() => useVoiceCapture(FAKE_ENCOUNTER_ID));
    expect(result.current.status).toBe("idle");
    expect(result.current.elapsedMs).toBe(0);
    expect(result.current.transcript).toBe("");
    expect(result.current.error).toBeNull();
  });

  it("コーデック非サポート: status=error、kind=unsupportedCodec", async () => {
    vi.stubGlobal("MediaRecorder", makeFakeMediaRecorder(false));
    const { result } = renderHook(() => useVoiceCapture(FAKE_ENCOUNTER_ID));
    await act(async () => {
      await result.current.start();
    });
    expect(result.current.status).toBe("error");
    expect(result.current.error?.kind).toBe("unsupportedCodec");
  });

  it("マイク権限拒否: status=permission_denied", async () => {
    Object.defineProperty(global.navigator, "mediaDevices", {
      value: {
        getUserMedia: vi.fn().mockRejectedValue(new DOMException("denied", "NotAllowedError")),
      },
      configurable: true,
      writable: true,
    });
    const { result } = renderHook(() => useVoiceCapture(FAKE_ENCOUNTER_ID));
    await act(async () => {
      await result.current.start();
    });
    expect(result.current.status).toBe("permission_denied");
    expect(result.current.error).toBeNull();
  });

  it("成功パス: transcript が設定され status=success になる", async () => {
    mockTranscribe.mockResolvedValueOnce({ kind: "success", text: "テスト文字起こし" });
    const { result } = renderHook(() => useVoiceCapture(FAKE_ENCOUNTER_ID));

    await act(async () => {
      await result.current.start();
    });

    // stop() を呼ぶと onstop → uploading → transcribeAudio が解決 → success
    await act(async () => {
      result.current.stop();
    });

    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(result.current.transcript).toBe("テスト文字起こし");
    expect(result.current.error).toBeNull();
  });

  it("503 → kind=transcriptionUnavailable エラー", async () => {
    mockTranscribe.mockResolvedValueOnce({ kind: "transcription_unavailable" });
    const { result } = renderHook(() => useVoiceCapture(FAKE_ENCOUNTER_ID));

    await act(async () => {
      await result.current.start();
    });
    await act(async () => {
      result.current.stop();
    });

    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.error?.kind).toBe("transcriptionUnavailable");
  });

  it("504 → kind=transcriptionTimeout エラー", async () => {
    mockTranscribe.mockResolvedValueOnce({ kind: "transcription_timeout" });
    const { result } = renderHook(() => useVoiceCapture(FAKE_ENCOUNTER_ID));

    await act(async () => {
      await result.current.start();
    });
    await act(async () => {
      result.current.stop();
    });

    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.error?.kind).toBe("transcriptionTimeout");
  });

  it("415 → kind=unsupportedCodec エラー", async () => {
    mockTranscribe.mockResolvedValueOnce({ kind: "unsupported_format" });
    const { result } = renderHook(() => useVoiceCapture(FAKE_ENCOUNTER_ID));

    await act(async () => {
      await result.current.start();
    });
    await act(async () => {
      result.current.stop();
    });

    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.error?.kind).toBe("unsupportedCodec");
  });

  it("encounter_not_found → kind=generic エラー", async () => {
    mockTranscribe.mockResolvedValueOnce({ kind: "encounter_not_found" });
    const { result } = renderHook(() => useVoiceCapture(FAKE_ENCOUNTER_ID));

    await act(async () => {
      await result.current.start();
    });
    await act(async () => {
      result.current.stop();
    });

    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.error?.kind).toBe("generic");
  });

  it("60 秒経過で自動停止: status が uploading に遷移する", async () => {
    // transcribeAudio は永遠に pending (タイムアウトテストのため)
    mockTranscribe.mockImplementation(() => new Promise<never>(() => undefined));

    vi.useFakeTimers();

    const { result } = renderHook(() => useVoiceCapture(FAKE_ENCOUNTER_ID));

    await act(async () => {
      await result.current.start();
    });
    expect(result.current.status).toBe("recording");

    // 60 秒分進める — advanceTimersByTimeAsync はマイクロタスクも flush する
    await act(async () => {
      await vi.advanceTimersByTimeAsync(AUDIO_MAX_DURATION_S * 1000 + 100);
    });

    // stop() が呼ばれ onstop → uploading に遷移しているはず
    // fake timers 下では waitFor の polling も fake setTimeout を使うため、
    // 直接 result を検査する
    expect(result.current.status).toBe("uploading");
  });

  it("recording 中に cancel(): status=idle に戻る", async () => {
    const { result } = renderHook(() => useVoiceCapture(FAKE_ENCOUNTER_ID));

    await act(async () => {
      await result.current.start();
    });
    expect(result.current.status).toBe("recording");

    act(() => {
      result.current.cancel();
    });

    expect(result.current.status).toBe("idle");
  });

  it("uploading 中に cancel(): status=idle に戻り transcribeAudio の AbortError を吸収する", async () => {
    // transcribeAudio は pending のまま
    mockTranscribe.mockImplementation(() => new Promise<never>(() => undefined));
    const { result } = renderHook(() => useVoiceCapture(FAKE_ENCOUNTER_ID));

    await act(async () => {
      await result.current.start();
    });
    // stop() → onstop() が同期実行されるため status は uploading になる
    await act(async () => {
      result.current.stop();
    });

    // onstop が同期実行されるため、act 後に status は uploading になっているはず
    expect(result.current.status).toBe("uploading");

    act(() => {
      result.current.cancel();
    });

    expect(result.current.status).toBe("idle");
  });

  it("localStorage.setItem が呼ばれないことを確認する", async () => {
    mockTranscribe.mockResolvedValueOnce({ kind: "success", text: "テスト" });
    const spy = vi.spyOn(Storage.prototype, "setItem");
    const { result } = renderHook(() => useVoiceCapture(FAKE_ENCOUNTER_ID));

    await act(async () => {
      await result.current.start();
    });
    await act(async () => {
      result.current.stop();
    });
    await waitFor(() => expect(result.current.status).toBe("success"));

    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// ストリーミングパス テスト (FE-013)
// ---------------------------------------------------------------------------

describe("useVoiceCapture — ストリーミングパス (ASR_STREAMING_ENABLED=true)", () => {
  beforeEach(() => {
    mockTranscribe.mockReset();
    mockStreamTranscribe.mockReset();
    // ストリーミングパスを有効化する
    vi.mocked(constants).ASR_STREAMING_ENABLED = true;

    vi.stubGlobal("MediaRecorder", makeFakeMediaRecorder(true));

    const fakeStream = makeFakeStream();
    Object.defineProperty(global.navigator, "mediaDevices", {
      value: { getUserMedia: vi.fn().mockResolvedValue(fakeStream) },
      configurable: true,
      writable: true,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.mocked(constants).ASR_STREAMING_ENABLED = false;
  });

  it("(a) 3 チャンク → complete: streaming フィールドが更新され、status=success + transcript が設定される", async () => {
    // streamTranscribeAudio をモック: onChunk × 3 → onComplete を順に呼ぶ
    mockStreamTranscribe.mockImplementation(async (_encId, _blob, opts) => {
      opts.onChunk("こんにちは", 0, 3);
      opts.onChunk("世界", 1, 3);
      opts.onChunk("！", 2, 3);
      opts.onComplete({ fullText: "こんにちは世界！", durationSeconds: 1.5, chunkCount: 3 });
    });

    const { result } = renderHook(() => useVoiceCapture(FAKE_ENCOUNTER_ID));

    await act(async () => {
      await result.current.start();
    });
    await act(async () => {
      result.current.stop();
    });

    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(result.current.transcript).toBe("こんにちは世界！");
    // success 後は streaming が null にクリアされる
    expect(result.current.streaming).toBeNull();
    // transcribeAudio (非ストリーミング) は呼ばれない
    expect(mockTranscribe).not.toHaveBeenCalled();
    expect(mockStreamTranscribe).toHaveBeenCalledTimes(1);
  });

  it("(b) ASR_STREAMING_ENABLED=false → transcribeAudio が呼ばれ、streamTranscribeAudio は呼ばれない", async () => {
    // このテストでは false に戻す
    vi.mocked(constants).ASR_STREAMING_ENABLED = false;
    mockTranscribe.mockResolvedValueOnce({ kind: "success", text: "テスト" });

    const { result } = renderHook(() => useVoiceCapture(FAKE_ENCOUNTER_ID));

    await act(async () => {
      await result.current.start();
    });
    await act(async () => {
      result.current.stop();
    });

    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(mockTranscribe).toHaveBeenCalledTimes(1);
    expect(mockStreamTranscribe).not.toHaveBeenCalled();
  });

  it("(c) ASR_STREAMING_ENABLED=true → streamTranscribeAudio が呼ばれ、transcribeAudio は呼ばれない", async () => {
    mockStreamTranscribe.mockImplementation(async (_encId, _blob, opts) => {
      opts.onComplete({ fullText: "テスト", durationSeconds: null, chunkCount: 1 });
    });

    const { result } = renderHook(() => useVoiceCapture(FAKE_ENCOUNTER_ID));

    await act(async () => {
      await result.current.start();
    });
    await act(async () => {
      result.current.stop();
    });

    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(mockStreamTranscribe).toHaveBeenCalledTimes(1);
    expect(mockTranscribe).not.toHaveBeenCalled();
  });

  it("(d) ストリーミング中に cancel() → バッファが破棄され streaming=null、status=idle、onTranscript は呼ばれない", async () => {
    // streamTranscribeAudio は AbortError をスローする (AbortController が abort された場合)
    let resolveAbort!: () => void;
    mockStreamTranscribe.mockImplementation(async (_encId, _blob, opts) => {
      // 最初の 1 チャンクを送る
      opts.onChunk("部分", 0, 3);
      // その後 abort されるまで pending
      return new Promise<void>((_resolve, reject) => {
        resolveAbort = () => reject(new DOMException("aborted", "AbortError"));
      });
    });

    const { result } = renderHook(() => useVoiceCapture(FAKE_ENCOUNTER_ID));

    await act(async () => {
      await result.current.start();
    });
    await act(async () => {
      result.current.stop();
    });

    // 1 チャンク到着後に streaming が設定されるのを待つ
    await waitFor(() => expect(result.current.streaming).not.toBeNull());

    // cancel() を呼ぶ → abort → AbortError が throw される
    await act(async () => {
      result.current.cancel();
      resolveAbort();
    });

    expect(result.current.status).toBe("idle");
    expect(result.current.streaming).toBeNull();
  });

  it("(e) ミッドストリーム transcription_unavailable → status=error、streaming=null、onTranscript 未呼び出し", async () => {
    mockStreamTranscribe.mockImplementation(async (_encId, _blob, opts) => {
      opts.onChunk("部分テキスト", 0, 3);
      opts.onError({ kind: "transcription_unavailable", chunkIndex: 1 });
    });

    const { result } = renderHook(() => useVoiceCapture(FAKE_ENCOUNTER_ID));

    await act(async () => {
      await result.current.start();
    });
    await act(async () => {
      result.current.stop();
    });

    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.streaming).toBeNull();
    expect(result.current.error?.kind).toBe("transcriptionUnavailable");
    expect(result.current.transcript).toBe("");
  });

  it("(f) ミッドストリーム transcription_timeout → status=error、タイムアウト JP 文言が設定される", async () => {
    mockStreamTranscribe.mockImplementation(async (_encId, _blob, opts) => {
      opts.onError({ kind: "transcription_timeout" });
    });

    const { result } = renderHook(() => useVoiceCapture(FAKE_ENCOUNTER_ID));

    await act(async () => {
      await result.current.start();
    });
    await act(async () => {
      result.current.stop();
    });

    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.error?.kind).toBe("transcriptionTimeout");
    expect(result.current.error?.message).toContain("録音を短くして");
  });
});
