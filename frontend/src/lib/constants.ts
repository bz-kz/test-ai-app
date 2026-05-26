/** モデル識別子 — SPEC.md#inference-layer-contract で固定。変更には ADR が必要。 */
export const LLM_MODEL = "gemma4:e4b";

/** レイテンシ閾値 (ms) — frontend/SPEC.md#latency-ux-budget */
export const LATENCY_SPINNER_MS = 300;
export const LATENCY_SKELETON_MS = 1000;
export const LATENCY_HINT_MS = 3000;
export const LATENCY_CANCEL_MS = 10000;

/**
 * 下書き生成の目安完了時間 (ms)。
 * CPU 推論実測 (Playwright 再現 2026-05-13): 4-5 分。中央値 4 分 = 240,000ms を 100% とするバー表示に使用。
 * SPEC ≤6s の budget は CPU バックエンドでは届かないため、UX 上は実測ベースの目安に切り替える (INF-006)。
 */
export const DRAFT_GENERATION_ETA_MS = 240_000;

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
  /** 60 秒で録音が自動停止したことを知らせる non-disruptive toast 文言 */
  autoStopped: "録音は60秒で停止しました",
} as const;

/** 音声入力レイテンシ UX 閾値 (ms) — frontend/SPEC.md#voice-input-latency-ux */
export const ASR_LATENCY_SPINNER_MS = 500;
export const ASR_LATENCY_HINT_MS = 3000;
export const ASR_LATENCY_CANCEL_MS = 10000;

/**
 * 音声キャプチャ状態表示文言 — frontend/SPEC.md#voice-input-latency-ux L113–L114
 * PHI を含まない固定文言のみ。
 */
export const VOICE_CAPTURE_STATUS = {
  /** 500ms–3s tier: スピナーと共に表示 (SPEC L113) */
  transcribing: "文字起こし中…",
  /** 3s–10s tier: ローカル ASR の応答待ちヒント (SPEC L114) */
  localAsrHint: "ローカル音声認識の応答待ち",
} as const;

/** ADR-0003: ストリーミング ASR 機能フラグ。デフォルト false → FE-009 の動作を維持する。 */
export const ASR_STREAMING_ENABLED = process.env.NEXT_PUBLIC_ASR_STREAMING_ENABLED === "true";

/**
 * ADR-0006 FE-015: Datadog Browser RUM 機能フラグ。デフォルト false。
 * NEXT_PUBLIC_* は build 時 bake のため flip には docker compose build frontend が必須。
 * applicationId / clientToken が設定されていない時は init 自体が no-op になるので、
 * このフラグは「環境差分での kill switch」用途。
 */
export const RUM_ENABLED = process.env.NEXT_PUBLIC_RUM_ENABLED === "true";

/** ADR-0003 ストリーミング: 最初のチャンク可視フィードバック目標 (ms) */
export const ASR_STREAM_FIRST_CHUNK_MS = 25000;

/**
 * 操作成功メッセージの自動非表示までのミリ秒。
 * 例: 「✓ 受診を追加しました」を一定時間後に非表示にする。
 */
export const CONFIRMATION_AUTO_HIDE_MS = 2000;
