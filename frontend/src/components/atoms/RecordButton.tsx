/**
 * RecordButton atom — マイク録音ボタン (idle / recording / uploading)
 *
 * DESIGN.md §Buttons に倣い 48×48px 円形ボタン。
 * - idle: マイクアイコン (黒)
 * - recording: 赤塗り + animate-pulse
 * - uploading: スピナー
 *
 * アクセシビリティ:
 * - role="button" (button 要素で自動付与)
 * - aria-pressed={state === "recording"}
 * - aria-label: 状態に応じたデフォルト JP 文言、または prop で上書き可
 * - disabled: 40% opacity + cursor-not-allowed (DESIGN.md §Disabled State と同じ)
 */
import React from "react";

export type RecordButtonState = "idle" | "recording" | "uploading";

export interface RecordButtonProps {
  state: RecordButtonState;
  onClick: () => void;
  disabled?: boolean;
  "aria-label"?: string;
}

const defaultLabels: Record<RecordButtonState, string> = {
  idle: "音声入力を開始",
  recording: "音声入力を停止",
  uploading: "アップロード中",
};

/** マイクアイコン — インライン SVG */
function MicIcon() {
  return (
    <svg width={22} height={22} viewBox="0 0 22 22" fill="none" aria-hidden="true">
      {/* マイク本体 */}
      <rect
        x="7.5"
        y="1.5"
        width="7"
        height="11"
        rx="3.5"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      {/* マイクスタンド */}
      <path
        d="M4 10.5a7 7 0 0 0 14 0"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <line
        x1="11"
        y1="17.5"
        x2="11"
        y2="20.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <line
        x1="8"
        y1="20.5"
        x2="14"
        y2="20.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** スピナー — Button.tsx の Spinner と同じパターン */
function Spinner() {
  return (
    <svg
      className="animate-spin"
      width={22}
      height={22}
      viewBox="0 0 22 22"
      fill="none"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="11" cy="11" r="9" stroke="currentColor" strokeWidth="2" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M20 11a9 9 0 0 1-9 9V18a7 7 0 0 0 7-7h2z"
      />
    </svg>
  );
}

/**
 * RecordButton atom。
 *
 * DESIGN.md §Accessibility Bar に準拠したフォーカスリングを持つ。
 */
export function RecordButton({
  state,
  onClick,
  disabled = false,
  "aria-label": ariaLabelProp,
}: RecordButtonProps) {
  const ariaLabel = ariaLabelProp ?? defaultLabels[state];
  const isRecording = state === "recording";

  // 状態別クラス
  const stateClasses =
    state === "idle"
      ? "bg-surface border border-navy text-navy hover:bg-navy/5"
      : state === "recording"
        ? "bg-error text-white animate-pulse border-0"
        : /* uploading */ "bg-surface border border-navy text-navy";

  const baseClasses =
    "inline-flex h-12 w-12 items-center justify-center rounded-full transition-colors" +
    " focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy focus-visible:ring-offset-2" +
    " disabled:opacity-40 disabled:cursor-not-allowed disabled:pointer-events-none";

  return (
    <button
      type="button"
      aria-label={ariaLabel}
      aria-pressed={isRecording}
      disabled={disabled}
      onClick={onClick}
      className={[baseClasses, stateClasses].join(" ")}
    >
      {state === "idle" && <MicIcon />}
      {state === "recording" && (
        /* 録音中: 塗りつぶし丸 (中央に白い小円) */
        <span aria-hidden="true" className="block h-4 w-4 rounded-full bg-white" />
      )}
      {state === "uploading" && <Spinner />}
    </button>
  );
}

export default RecordButton;
