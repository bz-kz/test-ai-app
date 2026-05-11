/**
 * 患者サービス層。
 *
 * fetch を所有し、apiFetch を通じて API を呼び出す。
 * PHI (mrn, family_name, given_name, date_of_birth) はログに出力しない。
 * コンポーネントやフックは直接 fetch を呼び出さず、このモジュールを使う。
 */
import { apiFetch } from "@/lib/api";
import type { Patient } from "@/types/patient";

/** searchPatientsByMrn の戻り値型 */
export type SearchPatientResult =
  | { kind: "found"; patient: Patient }
  | { kind: "not_found" }
  | { kind: "error" };

/** getPatientById の戻り値型 */
export type GetPatientResult =
  | { kind: "found"; patient: Patient }
  | { kind: "not_found" }
  | { kind: "error" };

/**
 * MRN で患者を検索する。
 *
 * - 見つかった場合: `{ kind: "found", patient }`
 * - 見つからない場合: `{ kind: "not_found" }`
 * - ネットワーク/サーバーエラー: `{ kind: "error" }`
 * - AbortController によるキャンセル: 例外を再スロー (useMrnSearch が処理する)
 *
 * @param mrn   診察番号 (PHI)
 * @param opts  AbortSignal など
 */
export async function searchPatientsByMrn(
  mrn: string,
  opts?: { signal?: AbortSignal }
): Promise<SearchPatientResult> {
  // MRN は PHI のため URL エンコードして渡すが、ログには出力しない
  const path = `/patients?mrn=${encodeURIComponent(mrn)}`;
  const result = await apiFetch<Patient>(path, { signal: opts?.signal });

  switch (result.kind) {
    case "ok":
      return { kind: "found", patient: result.data };
    case "not_found":
      return { kind: "not_found" };
    default:
      // validation_error / server_error / network_error はすべて error に統一
      return { kind: "error" };
  }
}

/**
 * 患者 ID で患者を取得する (GET /patients/{id})。
 *
 * - 見つかった場合: `{ kind: "found", patient }`
 * - 見つからない場合: `{ kind: "not_found" }`
 * - ネットワーク/サーバーエラー: `{ kind: "error" }`
 * - AbortController によるキャンセル: 例外を再スロー (呼び出し元が処理する)
 *
 * @param id   患者 UUID
 * @param opts AbortSignal など
 */
export async function getPatientById(
  id: string,
  opts?: { signal?: AbortSignal }
): Promise<GetPatientResult> {
  // patient_id は PHI との紐づきを持つため、ログには出力しない
  const path = `/patients/${encodeURIComponent(id)}`;
  const result = await apiFetch<Patient>(path, { signal: opts?.signal });

  switch (result.kind) {
    case "ok":
      return { kind: "found", patient: result.data };
    case "not_found":
      return { kind: "not_found" };
    default:
      // validation_error / server_error / network_error はすべて error に統一
      return { kind: "error" };
  }
}
