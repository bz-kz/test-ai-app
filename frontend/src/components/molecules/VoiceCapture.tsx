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

import React, { useEffect, useRef } from "react";
import RecordButton from "@/components/atoms/RecordButton";
import { useVoiceCapture } from "@/hooks/useVoiceCapture";
import {
  ASR_LATENCY_SPINNER_MS,
  ASR_LATENCY_HINT_MS,
  ASR_LATENCY_CANCEL_MS,
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
      className="inline animate-spin"
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
  const { status, elapsedMs, transcript, error, start, stop, cancel } =
    useVoiceCapture(encounterId);

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

  // RecordButton の state を決定する
  const buttonState: RecordButtonState =
    status === "recording" || status === "stopping"
      ? "recording"
      : status === "uploading"
        ? "uploading"
        : "idle";

  const handleClick = () => {
    if (status === "recording") {
      stop();
    } else if (status === "idle" || status === "error") {
      void start();
    }
  };

  // 録音中 / アップロード中 / permission-requested のとき外部 disabled に加えてロックする
  const isButtonDisabled =
    disabled ||
    status === "uploading" ||
    status === "stopping" ||
    status === "permission-requested";

  return (
    <div className="flex items-center gap-3">
      <RecordButton state={buttonState} onClick={handleClick} disabled={isButtonDisabled} />

      {/* ライブリージョン — PHI を含まない固定文言 / 時間のみ */}
      <div aria-live="polite" aria-atomic="true" className="min-w-0 text-sm text-slate">
        {/* 録音中: 経過時間 / 上限時間 */}
        {(status === "recording" || status === "stopping") && (
          <span>{formatElapsed(elapsedMs)} / 60s</span>
        )}

        {/* アップロード中 */}
        {status === "uploading" && (
          <span className="inline-flex items-center gap-1.5">
            {elapsedMs >= ASR_LATENCY_SPINNER_MS && <SmallSpinner />}
            {elapsedMs >= ASR_LATENCY_HINT_MS && <span>音声を文字起こし中…</span>}
            {elapsedMs >= ASR_LATENCY_CANCEL_MS && (
              <button type="button" className="ml-1 text-sm text-error underline" onClick={cancel}>
                キャンセル
              </button>
            )}
          </span>
        )}

        {/* エラー */}
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
