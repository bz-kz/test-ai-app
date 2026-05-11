/**
 * 確定カルテサービス層 (finals)。
 *
 * 別ファイル (finals.ts) とした理由: drafts.ts は下書きドメイン固有の関心事を持つ。
 * 確定カルテの訂正・チェーン取得は record_final ドメインに属し、
 * 責務が異なるため分離した (SRP + 将来の拡張を容易にする)。
 *
 * fetch を所有し、apiFetch を通じて API を呼び出す。
 * PHI (content, correction content) はログに出力しない。
 * コンポーネントやフックは直接 fetch を呼び出さず、このモジュールを使う。
 */
import { apiFetch } from "@/lib/api";
import type { RecordFinal } from "@/types/recordFinal";

/** correctRecordFinal の戻り値型 */
export type CorrectFinalResult =
  | { kind: "created"; final: RecordFinal }
  | { kind: "final_not_found" }
  | { kind: "validation_error"; fields: string[] }
  | { kind: "error" };

/** getFinalChain の戻り値型 */
export type GetChainResult =
  | { kind: "found"; chain: RecordFinal[] }
  | { kind: "not_found" }
  | { kind: "error" };

/**
 * 確定カルテの訂正版を作成する (POST /finals/{finalId}/correct)。
 *
 * - 成功 (201): `{ kind: "created", final }`
 * - 訂正元が存在しない (404): `{ kind: "final_not_found" }`
 * - バリデーションエラー (422): `{ kind: "validation_error", fields }`
 * - その他エラー: `{ kind: "error" }`
 *
 * @param finalId     訂正元確定カルテ UUID
 * @param content     訂正後の本文 (PHI) — ログに出力しない
 * @param clinicianId 臨床医 UUID
 * @param opts        AbortSignal など
 */
export async function correctRecordFinal(
  finalId: string,
  content: string,
  clinicianId: string,
  opts?: { signal?: AbortSignal }
): Promise<CorrectFinalResult> {
  const path = `/finals/${encodeURIComponent(finalId)}/correct`;

  const result = await apiFetch<RecordFinal>(path, {
    method: "POST",
    body: JSON.stringify({ content, clinician_id: clinicianId }),
    signal: opts?.signal,
  });

  switch (result.kind) {
    case "ok":
      return { kind: "created", final: result.data };

    case "not_found":
      return { kind: "final_not_found" };

    case "validation_error":
      return { kind: "validation_error", fields: result.fields };

    case "server_error":
      return { kind: "error" };

    case "network_error":
      return { kind: "error" };
  }
}

/**
 * 確定カルテの predecessor チェーンを取得する (GET /finals/{finalId}/chain)。
 *
 * - 成功: `{ kind: "found", chain }` — 配列は [最古版, ..., 指定版] の昇順
 * - 見つからない (404): `{ kind: "not_found" }`
 * - その他エラー: `{ kind: "error" }`
 *
 * @param finalId 確定カルテ UUID
 * @param opts    AbortSignal など
 */
export async function getFinalChain(
  finalId: string,
  opts?: { signal?: AbortSignal }
): Promise<GetChainResult> {
  const path = `/finals/${encodeURIComponent(finalId)}/chain`;

  const result = await apiFetch<RecordFinal[]>(path, {
    method: "GET",
    signal: opts?.signal,
  });

  switch (result.kind) {
    case "ok":
      return { kind: "found", chain: result.data };

    case "not_found":
      return { kind: "not_found" };

    case "validation_error":
    case "server_error":
    case "network_error":
      return { kind: "error" };
  }
}
