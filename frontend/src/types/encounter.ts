/**
 * Encounter ドメイン型 — SPEC.md#domain-glossary で定義された encounter に対応。
 * バックエンドの EncounterRead レスポンスと 1:1 に対応する。
 *
 * patient_id は PHI との紐づきを持つ — コンソールやストレージに出力しない。
 */
export interface Encounter {
  id: string;
  patient_id: string;
  encountered_at: string;
  clinician_id: string;
  created_at: string;
}
