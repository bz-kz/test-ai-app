/**
 * カルテ下書きサービス層。
 *
 * fetch を所有し、apiFetch を通じて API を呼び出す。
 * PHI (clinical_input, draft.content, final.content) はログに出力しない。
 * コンポーネントやフックは直接 fetch を呼び出さず、このモジュールを使う。
 *
 * 別ファイル (drafts.ts) とした理由: patients.ts は患者ドメイン固有の関心事を持つ。
 * 下書き生成は encounter/draft ドメインに属し、責務が異なるため分離した。
 */
import { apiFetch } from "@/lib/api";
import type { RecordDraft } from "@/types/recordDraft";
import type { RecordFinal } from "@/types/recordFinal";

/** createRecordDraft の戻り値型 */
export type CreateDraftResult =
  | { kind: "created"; draft: RecordDraft }
  | { kind: "encounter_not_found" }
  | { kind: "inference_unavailable" }
  | { kind: "validation_error"; fields: string[] }
  | { kind: "error" };

/** editRecordDraft の戻り値型 */
export type EditDraftResult =
  | { kind: "updated"; draft: RecordDraft }
  | { kind: "draft_not_found" }
  | { kind: "validation_error"; fields: string[] }
  | { kind: "error" };

/** finalizeRecordDraft の戻り値型 */
export type FinalizeDraftResult =
  | { kind: "finalized"; final: RecordFinal }
  | { kind: "draft_not_found" }
  | { kind: "encounter_already_finalized" }
  | { kind: "validation_error"; fields: string[] }
  | { kind: "error" };

/** getRecordFinalById の戻り値型 */
export type GetFinalResult =
  | { kind: "found"; final: RecordFinal }
  | { kind: "not_found" }
  | { kind: "error" };

/**
 * カルテ下書きを生成する。
 *
 * - 成功: `{ kind: "created", draft }`
 * - Encounter が存在しない: `{ kind: "encounter_not_found" }`
 * - 推論サービス利用不可 (503): `{ kind: "inference_unavailable" }`
 * - バリデーションエラー (422): `{ kind: "validation_error", fields }`
 * - その他エラー: `{ kind: "error" }`
 * - AbortController によるキャンセル: 例外を再スロー (useGenerateDraft が処理する)
 *
 * @param encounterId  受診 UUID
 * @param clinicalInput  臨床入力 (PHI) — ログに出力しない
 * @param opts  AbortSignal など
 */
export async function createRecordDraft(
  encounterId: string,
  clinicalInput: string,
  opts?: { signal?: AbortSignal }
): Promise<CreateDraftResult> {
  const path = `/encounters/${encodeURIComponent(encounterId)}/drafts`;

  const result = await apiFetch<RecordDraft>(path, {
    method: "POST",
    body: JSON.stringify({ clinical_input: clinicalInput }),
    signal: opts?.signal,
  });

  switch (result.kind) {
    case "ok":
      return { kind: "created", draft: result.data };

    case "not_found":
      return { kind: "encounter_not_found" };

    case "validation_error":
      return { kind: "validation_error", fields: result.fields };

    case "server_error":
      // 503 は推論サービス一時利用不可として扱う
      if (result.code === "503" || result.code === "inference_unavailable") {
        return { kind: "inference_unavailable" };
      }
      return { kind: "error" };

    case "network_error":
      return { kind: "error" };
  }
}

/**
 * カルテ下書きを編集する (PATCH /drafts/{draftId})。
 *
 * - 成功: `{ kind: "updated", draft }`
 * - 下書きが存在しない: `{ kind: "draft_not_found" }`
 * - バリデーションエラー: `{ kind: "validation_error", fields }`
 * - その他エラー: `{ kind: "error" }`
 *
 * @param draftId  下書き UUID
 * @param content  編集後の本文 (PHI) — ログに出力しない
 * @param clinicianId  臨床医 UUID
 * @param opts  AbortSignal など
 */
export async function editRecordDraft(
  draftId: string,
  content: string,
  clinicianId: string,
  opts?: { signal?: AbortSignal }
): Promise<EditDraftResult> {
  const path = `/drafts/${encodeURIComponent(draftId)}`;

  const result = await apiFetch<RecordDraft>(path, {
    method: "PATCH",
    body: JSON.stringify({ content, clinician_id: clinicianId }),
    signal: opts?.signal,
  });

  switch (result.kind) {
    case "ok":
      return { kind: "updated", draft: result.data };

    case "not_found":
      return { kind: "draft_not_found" };

    case "validation_error":
      return { kind: "validation_error", fields: result.fields };

    case "server_error":
      return { kind: "error" };

    case "network_error":
      return { kind: "error" };
  }
}

/**
 * カルテ下書きを確定カルテに昇格させる (POST /drafts/{draftId}/finalize)。
 *
 * - 成功: `{ kind: "finalized", final }`
 * - 下書きが存在しない: `{ kind: "draft_not_found" }`
 * - 受診に確定カルテが既に存在する: `{ kind: "encounter_already_finalized" }`
 * - バリデーションエラー: `{ kind: "validation_error", fields }`
 * - その他エラー: `{ kind: "error" }`
 *
 * @param draftId  下書き UUID
 * @param clinicianId  臨床医 UUID
 * @param opts  AbortSignal など
 */
export async function finalizeRecordDraft(
  draftId: string,
  clinicianId: string,
  opts?: { signal?: AbortSignal }
): Promise<FinalizeDraftResult> {
  const path = `/drafts/${encodeURIComponent(draftId)}/finalize`;

  const result = await apiFetch<RecordFinal>(path, {
    method: "POST",
    body: JSON.stringify({ clinician_id: clinicianId }),
    signal: opts?.signal,
  });

  switch (result.kind) {
    case "ok":
      return { kind: "finalized", final: result.data };

    case "not_found":
      return { kind: "draft_not_found" };

    case "validation_error":
      return { kind: "validation_error", fields: result.fields };

    case "server_error":
      // 409 は server_error として扱われ、code が "encounter_already_finalized" になる
      if (result.code === "encounter_already_finalized" || result.code === "409") {
        return { kind: "encounter_already_finalized" };
      }
      return { kind: "error" };

    case "network_error":
      return { kind: "error" };
  }
}

/**
 * 確定カルテを ID で取得する (GET /finals/{finalId})。
 *
 * - 成功: `{ kind: "found", final }`
 * - 見つからない: `{ kind: "not_found" }`
 * - その他エラー: `{ kind: "error" }`
 *
 * @param finalId  確定カルテ UUID
 * @param opts  AbortSignal など
 */
export async function getRecordFinalById(
  finalId: string,
  opts?: { signal?: AbortSignal }
): Promise<GetFinalResult> {
  const path = `/finals/${encodeURIComponent(finalId)}`;

  const result = await apiFetch<RecordFinal>(path, {
    method: "GET",
    signal: opts?.signal,
  });

  switch (result.kind) {
    case "ok":
      return { kind: "found", final: result.data };

    case "not_found":
      return { kind: "not_found" };

    case "validation_error":
    case "server_error":
    case "network_error":
      return { kind: "error" };
  }
}
