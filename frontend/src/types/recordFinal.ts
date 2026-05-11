/**
 * RecordFinal ドメイン型 — SPEC.md#domain-glossary で定義された record_final に対応。
 * バックエンドの FinalRead レスポンスと 1:1 に対応する。
 *
 * content は PHI (自由記述の臨床叙述) — コンソールやストレージに出力しない。
 * predecessor_id は訂正チェーンの前バージョン UUID (FE-005 スコープで利用)。
 */
export interface RecordFinal {
  id: string;
  encounter_id: string;
  content: string;
  confidence: number | null;
  clinician_id: string;
  predecessor_id: string | null;
  created_at: string;
}
