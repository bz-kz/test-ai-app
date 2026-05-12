/** モデル識別子 — SPEC.md#inference-layer-contract で固定。変更には ADR が必要。 */
export const LLM_MODEL = "gemma4:e4b";

/** レイテンシ閾値 (ms) — frontend/SPEC.md#latency-ux-budget */
export const LATENCY_SPINNER_MS = 300;
export const LATENCY_SKELETON_MS = 1000;
export const LATENCY_HINT_MS = 3000;
export const LATENCY_CANCEL_MS = 10000;

/** API ベース URL — 環境変数から読み取る */
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/**
 * PoC 用固定 clinician ID — 本番では認証フローに置き換える。
 * PHI のため localStorage には保存しない。メモリ内定数として保持する。
 */
export const CLINICIAN_ID = "00000000-0000-0000-0000-0000000a11ce";

/** 音声キャプチャ制限 — frontend/SPEC.md#voice-capture */
export const AUDIO_MAX_DURATION_S = 60;
export const AUDIO_MIME_TYPE = "audio/webm;codecs=opus";
/** バックエンドの最大受付サイズ (2 MB) に合わせる */
export const AUDIO_MAX_BYTES = 2 * 1024 * 1024;

/**
 * 音声入力失敗モード JP 文言 — frontend/SPEC.md#voice-capture
 * PHI を含まない固定文言のみ。
 */
export const VOICE_CAPTURE_ERRORS = {
  permissionDenied: "マイクへのアクセスが許可されていません。ブラウザ設定を確認してください。",
  transcriptionUnavailable:
    "音声の文字起こしサービスが一時的に利用できません。テキスト入力を使用してください。",
  transcriptionTimeout:
    "音声が長すぎたか、サーバが混雑しています。録音を短くしてもう一度お試しください。",
  unsupportedCodec:
    "このブラウザは音声録音に対応していません (WebM/Opus)。Chrome / Firefox / Edge をお試しください。",
  generic: "音声の文字起こしに失敗しました。",
} as const;

/** 音声入力レイテンシ UX 閾値 (ms) — frontend/SPEC.md#voice-input-latency-ux */
export const ASR_LATENCY_SPINNER_MS = 500;
export const ASR_LATENCY_HINT_MS = 3000;
export const ASR_LATENCY_CANCEL_MS = 10000;
