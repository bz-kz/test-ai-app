/**
 * Patient ドメイン型 — SPEC.md#domain-glossary で定義されたフィールド名を使用。
 * バックエンドの PatientRead レスポンスと 1:1 に対応する。
 */
export interface Patient {
  id: string;
  mrn: string;
  family_name: string;
  given_name: string;
  date_of_birth: string;
  created_at: string;
}
