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
