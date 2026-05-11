/**
 * 受診サービス層。
 *
 * fetch を所有し、apiFetch を通じて API を呼び出す。
 * PHI (patient_id と encounter の紐づき) はログに出力しない。
 * コンポーネントやフックは直接 fetch を呼び出さず、このモジュールを使う。
 *
 * NOTE: createEncounter のリクエストボディに clinician_id を含めない。
 * BE-012 の仕様により clinician_id は X-Clinician-Id ヘッダー経由で送信する (apiFetch 側で注入)。
 */
import { apiFetch } from "@/lib/api";
import type { Encounter } from "@/types/encounter";
import type { RecordDraft } from "@/types/recordDraft";
import type { RecordFinal } from "@/types/recordFinal";

/** listEncountersByPatient の戻り値型 */
export type ListEncountersResult =
  | { kind: "found"; encounters: Encounter[] }
  | { kind: "patient_not_found" }
  | { kind: "error" };

/** getEncounterById の戻り値型 */
export type GetEncounterResult =
  | { kind: "found"; encounter: Encounter }
  | { kind: "not_found" }
  | { kind: "error" };

/** createEncounter の戻り値型 */
export type CreateEncounterResult =
  | { kind: "created"; encounter: Encounter }
  | { kind: "patient_not_found" }
  | { kind: "validation_error"; fields: string[] }
  | { kind: "error" };

/** listDraftsByEncounterInService の戻り値型 (encounters サービス用の再エクスポートはしない — drafts.ts を使う) */

/** listFinalsByEncounter の戻り値型 */
export type ListFinalsResult = { kind: "found"; finals: RecordFinal[] } | { kind: "error" };

/** listDraftsByEncounter (encounters コンテキスト用) の戻り値型 */
export type ListEncounterDraftsResult =
  | { kind: "found"; drafts: RecordDraft[] }
  | { kind: "error" };

/**
 * 患者 ID に紐づく受診一覧を取得する (GET /patients/{patientId}/encounters)。
 *
 * - 成功: `{ kind: "found", encounters }` — 空配列のこともある (受診なし)
 * - 患者が存在しない (404): `{ kind: "patient_not_found" }`
 * - その他エラー: `{ kind: "error" }`
 *
 * @param patientId 患者 UUID
 * @param opts      AbortSignal など
 */
export async function listEncountersByPatient(
  patientId: string,
  opts?: { signal?: AbortSignal }
): Promise<ListEncountersResult> {
  const path = `/patients/${encodeURIComponent(patientId)}/encounters`;
  const result = await apiFetch<Encounter[]>(path, { signal: opts?.signal });

  switch (result.kind) {
    case "ok":
      return { kind: "found", encounters: result.data };
    case "not_found":
      return { kind: "patient_not_found" };
    case "validation_error":
    case "server_error":
    case "network_error":
      return { kind: "error" };
  }
}

/**
 * 受診 ID で受診を取得する (GET /encounters/{encounterId})。
 *
 * - 成功: `{ kind: "found", encounter }`
 * - 見つからない (404): `{ kind: "not_found" }`
 * - その他エラー: `{ kind: "error" }`
 *
 * @param encounterId 受診 UUID
 * @param opts        AbortSignal など
 */
export async function getEncounterById(
  encounterId: string,
  opts?: { signal?: AbortSignal }
): Promise<GetEncounterResult> {
  const path = `/encounters/${encodeURIComponent(encounterId)}`;
  const result = await apiFetch<Encounter>(path, { signal: opts?.signal });

  switch (result.kind) {
    case "ok":
      return { kind: "found", encounter: result.data };
    case "not_found":
      return { kind: "not_found" };
    case "validation_error":
    case "server_error":
    case "network_error":
      return { kind: "error" };
  }
}

/**
 * 新規受診を作成する (POST /encounters)。
 *
 * clinician_id はボディに含めない — X-Clinician-Id ヘッダー経由で apiFetch が注入する。
 *
 * - 成功 (201): `{ kind: "created", encounter }`
 * - 患者が存在しない (404): `{ kind: "patient_not_found" }`
 * - バリデーションエラー (422): `{ kind: "validation_error", fields }`
 * - その他エラー: `{ kind: "error" }`
 *
 * @param params.patient_id     患者 UUID
 * @param params.encountered_at 受診日時 (ISO 8601)
 * @param opts                  AbortSignal など
 */
export async function createEncounter(
  params: { patient_id: string; encountered_at: string },
  opts?: { signal?: AbortSignal }
): Promise<CreateEncounterResult> {
  const result = await apiFetch<Encounter>("/encounters", {
    method: "POST",
    // clinician_id はボディに含めない (BE-012 — X-Clinician-Id ヘッダーで送信)
    body: JSON.stringify({
      patient_id: params.patient_id,
      encountered_at: params.encountered_at,
    }),
    signal: opts?.signal,
  });

  switch (result.kind) {
    case "ok":
      return { kind: "created", encounter: result.data };
    case "not_found":
      return { kind: "patient_not_found" };
    case "validation_error":
      return { kind: "validation_error", fields: result.fields };
    case "server_error":
      return { kind: "error" };
    case "network_error":
      return { kind: "error" };
  }
}

/**
 * 受診に紐づく確定カルテ一覧を取得する (GET /encounters/{encounterId}/finals)。
 *
 * - 成功: `{ kind: "found", finals }` — 空配列のこともある
 * - その他エラー: `{ kind: "error" }`
 *
 * @param encounterId 受診 UUID
 * @param opts        AbortSignal など
 */
export async function listFinalsByEncounter(
  encounterId: string,
  opts?: { signal?: AbortSignal }
): Promise<ListFinalsResult> {
  const path = `/encounters/${encodeURIComponent(encounterId)}/finals`;
  const result = await apiFetch<RecordFinal[]>(path, { signal: opts?.signal });

  switch (result.kind) {
    case "ok":
      return { kind: "found", finals: result.data };
    case "not_found":
    case "validation_error":
    case "server_error":
    case "network_error":
      return { kind: "error" };
  }
}
