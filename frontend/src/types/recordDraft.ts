/**
 * RecordDraft ドメイン型 — SPEC.md#domain-glossary で定義された record_draft に対応。
 * バックエンドの DraftRead レスポンスと 1:1 に対応する。
 *
 * content は PHI (自由記述の臨床叙述) — コンソールやストレージに出力しない。
 */
export interface RecordDraft {
  id: string;
  encounter_id: string;
  content: string;
  confidence: number | null;
  created_at: string;
  updated_at: string;
}
