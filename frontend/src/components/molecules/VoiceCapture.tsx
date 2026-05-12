"use client";

/**
 * VoiceCapture molecule — RecordButton + ライブリージョン。
 *
 * useVoiceCapture フックを所有し、録音 → 文字起こし → onTranscript コールバックまでを
 * カプセル化する。
 *
 * PHI ルール (local-llm-and-phi.md §3/§4):
 * - aria-live リージョンには固定文言 / 経過時間のみ。transcript (PHI) はここで表示しない。
 * - encounterId / transcript を console.* に出力しない。
 */

import React, { useEffect, useRef, useState } from "react";
import RecordButton from "@/components/atoms/RecordButton";
import { useVoiceCapture } from "@/hooks/useVoiceCapture";
import {
  ASR_LATENCY_SPINNER_MS,
  ASR_LATENCY_HINT_MS,
  ASR_LATENCY_CANCEL_MS,
  VOICE_CAPTURE_ERRORS,
  AUDIO_MAX_DURATION_S,
} from "@/lib/constants";
import type { RecordButtonState } from "@/components/atoms/RecordButton";

export interface VoiceCaptureProps {
  encounterId: string;
  onTranscript: (text: string) => void;
  disabled?: boolean;
}

/** アップロード中スピナー — Button.tsx の Spinner と同じパターン */
function SmallSpinner() {
  return (
    <svg
      className="inline motion-safe:animate-spin"
      width={14}
      height={14}
      viewBox="0 0 14 14"
      fill="none"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="2" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M13 7a6 6 0 0 1-6 6V11a4 4 0 0 0 4-4h2z"
      />
    </svg>
  );
}

/** mm:ss 形式の経過時間文字列を生成する */
function formatElapsed(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${min}:${sec.toString().padStart(2, "0")}`;
}

/**
 * VoiceCapture molecule。
 *
 * onTranscript は success 後に一度だけ呼び出し、フックを idle にリセットする。
 */
export function VoiceCapture({ encounterId, onTranscript, disabled = false }: VoiceCaptureProps) {
  const { status, elapsedMs, transcript, error, autoStopped, start, stop, cancel } =
    useVoiceCapture(encounterId);

  // 60 秒自動停止トースト — uploading 遷移後かつ autoStopped フラグが立っているとき表示する
  const [showAutoStopToast, setShowAutoStopToast] = useState(false);
  const prevStatusRef = useRef<typeof status>("idle");

  useEffect(() => {
    const prevStatus = prevStatusRef.current;
    prevStatusRef.current = status;

    // recording → uploading かつ autoStopped フラグが立っている場合は toast を表示する
    if (prevStatus === "recording" && status === "uploading" && autoStopped) {
      setShowAutoStopToast(true);
    }
    // uploading が終わったら toast をクリアする
    if (status !== "uploading") {
      setShowAutoStopToast(false);
    }
  }, [status, autoStopped]);

  // success → onTranscript を一度だけ呼び出す (useEffect の依存: status + transcript)
  const calledRef = useRef(false);
  useEffect(() => {
    if (status === "success" && !calledRef.current) {
      calledRef.current = true;
      onTranscript(transcript);
      // success 後は cancel() で idle に戻す (cancel は recording 以外でもクリーンアップのみ実行)
      cancel();
    }
    if (status !== "success") {
      calledRef.current = false;
    }
  }, [status, transcript, onTranscript, cancel]);

  // RecordButton の state を決定する (stopping を除去: recording → uploading に直接遷移)
  const buttonState: RecordButtonState =
    status === "recording" ? "recording" : status === "uploading" ? "uploading" : "idle";

  const handleClick = () => {
    if (status === "recording") {
      stop();
    } else if (status === "idle" || status === "error" || status === "permission_denied") {
      void start();
    }
  };

  // 録音中 / アップロード中 / requesting_permission のとき外部 disabled に加えてロックする
  const isButtonDisabled = disabled || status === "uploading" || status === "requesting_permission";

  return (
    <div className="flex items-center gap-3">
      <RecordButton state={buttonState} onClick={handleClick} disabled={isButtonDisabled} />

      {/* ライブリージョン — PHI を含まない固定文言 / 時間のみ */}
      <div aria-live="polite" aria-atomic="true" className="min-w-0 text-sm text-slate">
        {/* 録音中: 経過時間 / 上限時間 */}
        {status === "recording" && (
          <span>
            {formatElapsed(elapsedMs)} / {AUDIO_MAX_DURATION_S}s
          </span>
        )}

        {/* アップロード中 */}
        {status === "uploading" && (
          <span className="inline-flex items-center gap-1.5">
            {elapsedMs >= ASR_LATENCY_SPINNER_MS && (
              <>
                {/* prefers-reduced-motion: スピナーは motion-safe クラスで制御、静的省略記号に切り替え */}
                <span className="motion-safe:hidden">…</span>
                <SmallSpinner />
              </>
            )}
            {elapsedMs >= ASR_LATENCY_HINT_MS && <span>音声を文字起こし中…</span>}
            {elapsedMs >= ASR_LATENCY_CANCEL_MS && (
              <button type="button" className="ml-1 text-sm text-error underline" onClick={cancel}>
                キャンセル
              </button>
            )}
          </span>
        )}

        {/* 60 秒自動停止 toast — role="status" で非割り込みアナウンス */}
        {showAutoStopToast && (
          <span role="status" className="text-slate">
            {VOICE_CAPTURE_ERRORS.autoStopped}
          </span>
        )}

        {/* マイク権限拒否 */}
        {status === "permission_denied" && (
          <span role="alert" className="text-error">
            {VOICE_CAPTURE_ERRORS.permissionDenied}
          </span>
        )}

        {/* その他のエラー */}
        {status === "error" && error !== null && (
          <span role="alert" className="text-error">
            {error.message}
          </span>
        )}
      </div>
    </div>
  );
}

export default VoiceCapture;
