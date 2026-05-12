import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useVoiceCapture } from "../useVoiceCapture";
import { AUDIO_MAX_DURATION_S, AUDIO_MIME_TYPE } from "@/lib/constants";

// transcribe サービスをモック — 実際の fetch は呼び出さない
vi.mock("@/services/transcribe", () => ({
  transcribeAudio: vi.fn(),
}));

import { transcribeAudio } from "@/services/transcribe";
const mockTranscribe = vi.mocked(transcribeAudio);

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
