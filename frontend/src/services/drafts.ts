/**
 * カルテ下書きサービス層。
 *
 * fetch を所有し、apiFetch を通じて API を呼び出す。
 * PHI (clinical_input, draft.content) はログに出力しない。
 * コンポーネントやフックは直接 fetch を呼び出さず、このモジュールを使う。
 *
 * 別ファイル (drafts.ts) とした理由: patients.ts は患者ドメイン固有の関心事を持つ。
 * 下書き生成は encounter/draft ドメインに属し、責務が異なるため分離した。
 */
import { apiFetch } from "@/lib/api";
import type { RecordDraft } from "@/types/recordDraft";

/** createRecordDraft の戻り値型 */
export type CreateDraftResult =
  | { kind: "created"; draft: RecordDraft }
  | { kind: "encounter_not_found" }
  | { kind: "inference_unavailable" }
  | { kind: "validation_error"; fields: string[] }
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
