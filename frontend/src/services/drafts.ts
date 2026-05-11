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
import { API_BASE_URL, CLINICIAN_ID } from "@/lib/constants";
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
 * @param opts  AbortSignal など
 *
 * clinician_id は X-Clinician-Id ヘッダー経由で送信される (BE-012)。
 * body 側で受け付けると backend Pydantic `extra="forbid"` で 422 になる。
 */
export async function editRecordDraft(
  draftId: string,
  content: string,
  opts?: { signal?: AbortSignal }
): Promise<EditDraftResult> {
  const path = `/drafts/${encodeURIComponent(draftId)}`;

  const result = await apiFetch<RecordDraft>(path, {
    method: "PATCH",
    body: JSON.stringify({ content }),
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
 * @param opts  AbortSignal など
 *
 * clinician_id は X-Clinician-Id ヘッダー経由で送信される (BE-012)。
 * body 側で受け付けると backend Pydantic `extra="forbid"` で 422 になる。
 */
export async function finalizeRecordDraft(
  draftId: string,
  opts?: { signal?: AbortSignal }
): Promise<FinalizeDraftResult> {
  const path = `/drafts/${encodeURIComponent(draftId)}/finalize`;

  const result = await apiFetch<RecordFinal>(path, {
    method: "POST",
    body: JSON.stringify({}),
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

/** listDraftsByEncounter の戻り値型 */
export type ListDraftsResult = { kind: "found"; drafts: RecordDraft[] } | { kind: "error" };

/**
 * エンカウンターに紐づく下書き一覧を取得する (GET /encounters/{encounterId}/drafts)。
 *
 * バックエンドは 200 + 空配列 (encounter 不明の場合も含む) を返すため not_found タグは不要。
 * 返却順は created_at DESC (最新が先頭) — バックエンド BE-009 の契約に従う。
 *
 * - 成功: `{ kind: "found", drafts }` — 空配列のこともある
 * - その他エラー: `{ kind: "error" }`
 *
 * PHI (drafts[].content) はログに出力しない。
 *
 * @param encounterId  受診 UUID
 * @param opts  AbortSignal など
 */
export async function listDraftsByEncounter(
  encounterId: string,
  opts?: { signal?: AbortSignal }
): Promise<ListDraftsResult> {
  const path = `/encounters/${encodeURIComponent(encounterId)}/drafts`;

  const result = await apiFetch<RecordDraft[]>(path, {
    method: "GET",
    signal: opts?.signal,
  });

  switch (result.kind) {
    case "ok":
      return { kind: "found", drafts: result.data };

    case "not_found":
    case "validation_error":
    case "server_error":
    case "network_error":
      return { kind: "error" };
  }
}

/** streamRecordDraft の onError に渡すエラー種別 */
export type StreamDraftErrorKind =
  | "encounter_not_found"
  | "validation_error"
  | "inference_unavailable"
  | "error";

/** streamRecordDraft のコールバック群 */
export interface StreamDraftOpts {
  /** チャンク到着ごとに呼ばれる。text は今回届いたテキスト片 (PHI — ログ不可) */
  onChunk: (text: string) => void;
  /** ストリーム完了時に呼ばれる */
  onComplete: (info: { draftId: string; confidence: number | null }) => void;
  /** エラー発生時に呼ばれる */
  onError: (info: { kind: StreamDraftErrorKind }) => void;
  /** AbortSignal — セットされていればキャンセルに使う */
  signal?: AbortSignal;
}

/**
 * SSE ストリーミングで下書きを生成する (POST /encounters/{id}/drafts/stream)。
 *
 * BE-013 の SSE フレーム形式:
 *   - チャンク: `data: {"text":"...","done":false,"confidence":null}\n\n`
 *   - 完了:     `event: complete\ndata: {"draft_id":"...","confidence":<number|null>}\n\n`
 *   - エラー:   `event: error\ndata: {"code":"...","message":"..."}\n\n`
 *
 * 同期エラー (HTTP 404/422/503 など) はストリーム開始前に onError を呼ぶ。
 * PHI (clinical_input, chunk text, assembled content) はログに出力しない。
 *
 * @param encounterId  受診 UUID
 * @param clinicalInput  臨床入力 (PHI)
 * @param opts  コールバック群 + AbortSignal
 */
export async function streamRecordDraft(
  encounterId: string,
  clinicalInput: string,
  opts: StreamDraftOpts
): Promise<void> {
  const url = `${API_BASE_URL}/encounters/${encodeURIComponent(encounterId)}/drafts/stream`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // BE-012 の clinician_id ヘッダー — apiFetch と同じ定数を使う
        "X-Clinician-Id": CLINICIAN_ID,
      },
      body: JSON.stringify({ clinical_input: clinicalInput }),
      signal: opts.signal,
    });
  } catch (err) {
    // AbortError はキャンセルの正常系 — 呼び出し元 (hook) が処理する
    if (err instanceof DOMException && err.name === "AbortError") {
      throw err;
    }
    opts.onError({ kind: "error" });
    return;
  }

  // 同期エラー: ストリーム開始前に HTTP ステータスで判定する
  if (!response.ok) {
    if (response.status === 404) {
      opts.onError({ kind: "encounter_not_found" });
    } else if (response.status === 422) {
      opts.onError({ kind: "validation_error" });
    } else if (response.status === 503) {
      opts.onError({ kind: "inference_unavailable" });
    } else {
      opts.onError({ kind: "error" });
    }
    return;
  }

  // ストリーム読み取り
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  // バッファ: 未処理の受信テキストを蓄積する
  let buffer = "";

  /**
   * SSE フレームを解析してコールバックを呼び出す。
   * フレームは `\n\n` で区切られ、各行は `event:` または `data:` で始まる。
   * event 行のないフレームはデータチャンクとして扱う。
   */
  function processFrames(raw: string): void {
    // フレームは `\n\n` で分割する
    const frames = raw.split("\n\n");
    for (const frame of frames) {
      if (frame.trim() === "") continue;

      let eventType: string | null = null;
      let dataLine: string | null = null;

      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) {
          eventType = line.slice("event:".length).trim();
        } else if (line.startsWith("data:")) {
          dataLine = line.slice("data:".length).trim();
        }
      }

      if (dataLine === null) continue;

      // JSON パース失敗は静かにスキップ (不完全フレームは次のチャンクで補完)
      let parsed: unknown;
      try {
        parsed = JSON.parse(dataLine) as unknown;
      } catch {
        continue;
      }

      if (eventType === "complete") {
        // 完了フレーム: { draft_id, confidence }
        const p = parsed as Record<string, unknown>;
        const draftId = typeof p["draft_id"] === "string" ? p["draft_id"] : "";
        const confidence = typeof p["confidence"] === "number" ? p["confidence"] : null;
        opts.onComplete({ draftId, confidence });
      } else if (eventType === "error") {
        // エラーフレーム: { code, message }
        const p = parsed as Record<string, unknown>;
        const code = typeof p["code"] === "string" ? p["code"] : "";
        let kind: StreamDraftErrorKind;
        switch (code) {
          case "encounter_not_found":
            kind = "encounter_not_found";
            break;
          case "inference_unavailable":
            kind = "inference_unavailable";
            break;
          default:
            kind = "error";
        }
        opts.onError({ kind });
      } else {
        // データチャンク: { text, done, confidence }
        const p = parsed as Record<string, unknown>;
        const text = typeof p["text"] === "string" ? p["text"] : "";
        if (text !== "") {
          opts.onChunk(text);
        }
      }
    }
  }

  try {
    while (true) {
      // signal.aborted を読み取り前に確認する
      if (opts.signal?.aborted) {
        reader.cancel().catch(() => undefined);
        return;
      }

      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // バッファを `\n\n` で分割し、最後の要素 (未完了フレームの可能性) は残す
      const lastSep = buffer.lastIndexOf("\n\n");
      if (lastSep !== -1) {
        const toProcess = buffer.slice(0, lastSep + 2);
        buffer = buffer.slice(lastSep + 2);
        processFrames(toProcess);
      }
    }

    // ストリーム終端: 残バッファを処理する
    if (buffer.trim() !== "") {
      processFrames(buffer);
    }
  } catch (err) {
    // AbortError はキャンセルの正常系
    if (err instanceof DOMException && err.name === "AbortError") {
      throw err;
    }
    opts.onError({ kind: "error" });
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
