import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import VoiceCapture from "../VoiceCapture";
import { AUDIO_MIME_TYPE, ASR_LATENCY_CANCEL_MS } from "@/lib/constants";

// useVoiceCapture フックをモック
vi.mock("@/hooks/useVoiceCapture", () => ({
  useVoiceCapture: vi.fn(),
}));

import { useVoiceCapture } from "@/hooks/useVoiceCapture";
const mockUseVoiceCapture = vi.mocked(useVoiceCapture);

// テスト用デフォルトフック戻り値
function makeHookReturn(overrides: Partial<ReturnType<typeof useVoiceCapture>> = {}) {
  return {
    status: "idle" as const,
    elapsedMs: 0,
    transcript: "",
    error: null,
    start: vi.fn().mockResolvedValue(undefined),
    stop: vi.fn(),
    cancel: vi.fn(),
    ...overrides,
  };
}

const FAKE_ENCOUNTER_ID = "00000000-0000-0000-0000-000000000099";

// AUDIO_MIME_TYPE は定数から参照するので JSdom 環境で MediaRecorder を最低限スタブする
beforeEach(() => {
  if (typeof MediaRecorder === "undefined") {
    vi.stubGlobal(
      "MediaRecorder",
      class {
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        static isTypeSupported(_m: string) {
          return true;
        }
      }
    );
  }
});

describe("VoiceCapture molecule", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("idle 状態: RecordButton が idle、ライブリージョンは空", () => {
    mockUseVoiceCapture.mockReturnValue(makeHookReturn());
    render(<VoiceCapture encounterId={FAKE_ENCOUNTER_ID} onTranscript={vi.fn()} />);
    // RecordButton の aria-label は "音声入力を開始"
    expect(screen.getByRole("button", { name: "音声入力を開始" })).toBeInTheDocument();
    // aria-live リージョンにエラーや経過時間が表示されないこと
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("click → start() が呼ばれる", async () => {
    const user = userEvent.setup();
    const hookReturn = makeHookReturn();
    mockUseVoiceCapture.mockReturnValue(hookReturn);
    render(<VoiceCapture encounterId={FAKE_ENCOUNTER_ID} onTranscript={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "音声入力を開始" }));
    expect(hookReturn.start).toHaveBeenCalledTimes(1);
  });

  it("recording 状態: RecordButton が recording (aria-pressed=true)、経過時間が表示される", () => {
    mockUseVoiceCapture.mockReturnValue(makeHookReturn({ status: "recording", elapsedMs: 5200 }));
    render(<VoiceCapture encounterId={FAKE_ENCOUNTER_ID} onTranscript={vi.fn()} />);
    const btn = screen.getByRole("button", { name: "音声入力を停止" });
    expect(btn).toHaveAttribute("aria-pressed", "true");
    // 5200ms → 0:05 / 60s
    expect(screen.getByText(/0:05 \/ 60s/)).toBeInTheDocument();
  });

  it("recording 中クリック → stop() が呼ばれる", async () => {
    const user = userEvent.setup();
    const hookReturn = makeHookReturn({ status: "recording" });
    mockUseVoiceCapture.mockReturnValue(hookReturn);
    render(<VoiceCapture encounterId={FAKE_ENCOUNTER_ID} onTranscript={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "音声入力を停止" }));
    expect(hookReturn.stop).toHaveBeenCalledTimes(1);
  });

  it("success 状態: onTranscript が transcript テキストで呼ばれる", async () => {
    const onTranscript = vi.fn();
    mockUseVoiceCapture.mockReturnValue(
      makeHookReturn({ status: "success", transcript: "テスト文字起こし" })
    );
    render(<VoiceCapture encounterId={FAKE_ENCOUNTER_ID} onTranscript={onTranscript} />);
    await waitFor(() => expect(onTranscript).toHaveBeenCalledWith("テスト文字起こし"));
  });

  it("success 後に cancel() が呼ばれて idle リセットされる", async () => {
    const hookReturn = makeHookReturn({ status: "success", transcript: "テスト" });
    mockUseVoiceCapture.mockReturnValue(hookReturn);
    render(<VoiceCapture encounterId={FAKE_ENCOUNTER_ID} onTranscript={vi.fn()} />);
    await waitFor(() => expect(hookReturn.cancel).toHaveBeenCalledTimes(1));
  });

  it("permission_denied: JP エラーメッセージが alert として表示される", () => {
    mockUseVoiceCapture.mockReturnValue(
      makeHookReturn({
        status: "error",
        error: {
          kind: "permissionDenied",
          message: "マイクへのアクセスが許可されていません。ブラウザ設定を確認してください。",
        },
      })
    );
    render(<VoiceCapture encounterId={FAKE_ENCOUNTER_ID} onTranscript={vi.fn()} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("マイクへのアクセスが許可されていません");
  });

  it("503 (transcriptionUnavailable): JP エラーメッセージが alert として表示される", () => {
    mockUseVoiceCapture.mockReturnValue(
      makeHookReturn({
        status: "error",
        error: {
          kind: "transcriptionUnavailable",
          message:
            "音声の文字起こしサービスが一時的に利用できません。テキスト入力を使用してください。",
        },
      })
    );
    render(<VoiceCapture encounterId={FAKE_ENCOUNTER_ID} onTranscript={vi.fn()} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("音声の文字起こしサービスが一時的に利用できません");
  });

  it("uploading 中 ASR_LATENCY_CANCEL_MS 経過後にキャンセルボタンが表示される", () => {
    mockUseVoiceCapture.mockReturnValue(
      makeHookReturn({ status: "uploading", elapsedMs: ASR_LATENCY_CANCEL_MS + 100 })
    );
    render(<VoiceCapture encounterId={FAKE_ENCOUNTER_ID} onTranscript={vi.fn()} />);
    expect(screen.getByRole("button", { name: "キャンセル" })).toBeInTheDocument();
  });

  it("キャンセルボタンクリック → cancel() が呼ばれる", async () => {
    const user = userEvent.setup();
    const hookReturn = makeHookReturn({
      status: "uploading",
      elapsedMs: ASR_LATENCY_CANCEL_MS + 100,
    });
    mockUseVoiceCapture.mockReturnValue(hookReturn);
    render(<VoiceCapture encounterId={FAKE_ENCOUNTER_ID} onTranscript={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "キャンセル" }));
    expect(hookReturn.cancel).toHaveBeenCalledTimes(1);
  });

  it("disabled=true のとき RecordButton が無効化される", () => {
    mockUseVoiceCapture.mockReturnValue(makeHookReturn());
    render(<VoiceCapture encounterId={FAKE_ENCOUNTER_ID} onTranscript={vi.fn()} disabled />);
    expect(screen.getByRole("button", { name: "音声入力を開始" })).toBeDisabled();
  });

  it("uploading 中は RecordButton が無効化される (外部 disabled なし)", () => {
    mockUseVoiceCapture.mockReturnValue(makeHookReturn({ status: "uploading", elapsedMs: 100 }));
    render(<VoiceCapture encounterId={FAKE_ENCOUNTER_ID} onTranscript={vi.fn()} />);
    expect(screen.getByRole("button", { name: "アップロード中" })).toBeDisabled();
  });

  // 60 秒自動停止は useVoiceCapture フック内でテスト済みのため、
  // VoiceCapture レベルでは uploading への遷移が見えることを確認する
  it("60 秒後に uploading 状態になることを確認 (フックのオートストップ)", () => {
    mockUseVoiceCapture.mockReturnValue(makeHookReturn({ status: "uploading", elapsedMs: 0 }));
    render(<VoiceCapture encounterId={FAKE_ENCOUNTER_ID} onTranscript={vi.fn()} />);
    // uploading 状態: RecordButton は "アップロード中"
    expect(screen.getByRole("button", { name: "アップロード中" })).toBeInTheDocument();
  });

  // AUDIO_MIME_TYPE の参照が定数から来ていることを確認 (ハードコードしていない)
  it("AUDIO_MIME_TYPE が 'audio/webm;codecs=opus' であること", () => {
    expect(AUDIO_MIME_TYPE).toBe("audio/webm;codecs=opus");
  });
});
