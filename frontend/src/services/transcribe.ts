/**
 * 音声文字起こしサービス層。
 *
 * multipart/form-data で音声 Blob を POST /encounters/{id}/transcribe に送信する。
 * apiFetch は Content-Type を自動設定するため、multipart には生 fetch を使う
 * (apiFetch が JSON Content-Type を強制するため、FormData との互換性がない)。
 * この例外は drafts.ts の streamRecordDraft (FE-008) と同じ理由による。
 *
 * streamTranscribeAudio は POST /encounters/{id}/transcribe/stream (BE-017) を消費する。
 * SSE フレーム解析は streamRecordDraft と同じ \n\n 区切り + event:/data: 構造を使う。
 *
 * PHI ルール (local-llm-and-phi.md §3):
 * - 音声 Blob、チャンクテキスト、文字起こしテキスト、encounterId を console.* に出力しない。
 * - Blob リファレンスはこのモジュール外に保持しない (引数で受け取り、使い終わる)。
 */
import { API_BASE_URL, CLINICIAN_ID } from "@/lib/constants";

/** transcribeAudio の戻り値型 — 呼び出し元フックが状態機械に変換する */
export type TranscribeResult =
  | { kind: "success"; text: string; durationMs?: number }
  /** caller-side: hook がサービス呼び出し前にセットするため、ここでは定義のみ */
  | { kind: "permission_denied" }
  | { kind: "encounter_not_found" }
  | { kind: "validation_error"; fields: string[] }
  | { kind: "unsupported_format" }
  | { kind: "transcription_unavailable" }
  | { kind: "transcription_timeout" }
  | { kind: "error" };

/**
 * 音声 Blob を文字起こしエンドポイントに送信する。
 *
 * - 成功 (200): `{ kind: "success", text, durationMs? }`
 * - 404: `{ kind: "encounter_not_found" }`
 * - 415: `{ kind: "unsupported_format" }`
 * - 422: `{ kind: "validation_error", fields }`
 * - 503: `{ kind: "transcription_unavailable" }`
 * - 504: `{ kind: "transcription_timeout" }`
 * - ネットワーク障害 / その他: `{ kind: "error" }`
 * - AbortError: 再スロー (呼び出し元フックが処理する)
 *
 * @param encounterId  受診 UUID (PHI — ログに出力しない)
 * @param audio        音声 Blob (PHI — ログに出力しない)
 * @param opts         AbortSignal など
 */
export async function transcribeAudio(
  encounterId: string,
  audio: Blob,
  opts?: { signal?: AbortSignal }
): Promise<TranscribeResult> {
  const url = `${API_BASE_URL}/encounters/${encodeURIComponent(encounterId)}/transcribe`;

  const body = new FormData();
  body.append("audio", audio, "recording.webm");

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        // multipart/form-data の Content-Type は fetch が自動設定するため手動指定しない。
        // X-Clinician-Id のみ明示的に追加する (apiFetch と同じ定数)。
        "X-Clinician-Id": CLINICIAN_ID,
      },
      body,
      signal: opts?.signal,
    });
  } catch (err) {
    // AbortError はキャンセルの正常系 — 呼び出し元に伝播させる
    if (err instanceof DOMException && err.name === "AbortError") {
      throw err;
    }
    return { kind: "error" };
  }

  if (response.ok) {
    type SuccessBody = { text: string; duration_ms?: number };
    const data = (await response.json().catch(() => ({ text: "" }))) as SuccessBody;
    return {
      kind: "success",
      text: data.text ?? "",
      durationMs: data.duration_ms,
    };
  }

  switch (response.status) {
    case 404:
      return { kind: "encounter_not_found" };
    case 415:
      return { kind: "unsupported_format" };
    case 422: {
      type ValidationDetail = { loc?: string[]; msg?: string };
      type ValidationBody = { detail?: ValidationDetail[] | string };
      const body422 = (await response.json().catch(() => ({}))) as ValidationBody;
      const fields: string[] = [];
      if (Array.isArray(body422.detail)) {
        for (const item of body422.detail) {
          if (item.loc && item.loc.length > 0) {
            fields.push(item.loc[item.loc.length - 1] ?? "unknown");
          }
        }
      }
      return { kind: "validation_error", fields };
    }
    case 503:
      return { kind: "transcription_unavailable" };
    case 504:
      return { kind: "transcription_timeout" };
    default:
      return { kind: "error" };
  }
}

// ---------------------------------------------------------------------------
// streamTranscribeAudio — FE-013 / ADR-0003
// ---------------------------------------------------------------------------

/**
 * streamTranscribeAudio のエラー種別。
 * transcribeAudio の TranscribeResult の kind と対応させる。
 */
export type TranscribeStreamErrorKind =
  | "encounter_not_found"
  | "validation_error"
  | "unsupported_format"
  | "transcription_unavailable"
  | "transcription_timeout"
  | "error";

/** streamTranscribeAudio のコールバック群 */
export interface StreamTranscribeOpts {
  /** チャンク到着時に呼ばれる。PHI: テキストを console.* に出力しない。 */
  onChunk: (text: string, chunkIndex: number, chunkCount: number) => void;
  /** ストリーム完了時に呼ばれる。 */
  onComplete: (info: {
    fullText: string;
    durationSeconds: number | null;
    chunkCount: number;
  }) => void;
  /** エラー発生時に呼ばれる。 */
  onError: (info: { kind: TranscribeStreamErrorKind; chunkIndex?: number }) => void;
  /** AbortSignal — ストリームをキャンセルするために使う。 */
  signal?: AbortSignal;
}

/**
 * JSON オブジェクト型ガード (streamRecordDraft と同じパターン — FE-011 hardening)。
 * 数値・文字列・配列などの非オブジェクト値を不正フレームとして除外する。
 */
function isJsonObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * 音声 Blob をストリーミング文字起こしエンドポイントに送信する (FE-013)。
 *
 * - チャンク到着時: `onChunk(text, chunkIndex, chunkCount)` を呼ぶ。
 * - ストリーム完了時: `onComplete({ fullText, durationSeconds, chunkCount })` を呼ぶ。
 * - エラー時: `onError({ kind, chunkIndex? })` を呼ぶ。
 * - AbortError: 再スロー (呼び出し元フックが処理する)。
 *
 * multipart + SSE の組み合わせは apiFetch に対応していないため生 fetch を使う
 * (streamRecordDraft (FE-008) と同じ先例)。
 *
 * PHI ルール: チャンクテキスト・encounterId・Blob を console.* に出力しない。
 *
 * @param encounterId  受診 UUID (PHI — ログに出力しない)
 * @param audio        音声 Blob (PHI — ログに出力しない)
 * @param opts         コールバック群 + AbortSignal
 */
export async function streamTranscribeAudio(
  encounterId: string,
  audio: Blob,
  opts: StreamTranscribeOpts
): Promise<void> {
  const url = `${API_BASE_URL}/encounters/${encodeURIComponent(encounterId)}/transcribe/stream`;

  const body = new FormData();
  body.append("audio", audio, "recording.webm");

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        // multipart/form-data の Content-Type は fetch が自動設定するため手動指定しない。
        "X-Clinician-Id": CLINICIAN_ID,
      },
      body,
      signal: opts.signal,
    });
  } catch (err) {
    // AbortError はキャンセルの正常系 — 呼び出し元に伝播させる
    if (err instanceof DOMException && err.name === "AbortError") {
      throw err;
    }
    opts.onError({ kind: "error" });
    return;
  }

  // 同期エラー: ストリーム開始前に HTTP ステータスで判定する
  if (!response.ok) {
    switch (response.status) {
      case 404:
        opts.onError({ kind: "encounter_not_found" });
        break;
      case 415:
        opts.onError({ kind: "unsupported_format" });
        break;
      case 422:
        opts.onError({ kind: "validation_error" });
        break;
      case 503:
        opts.onError({ kind: "transcription_unavailable" });
        break;
      default:
        opts.onError({ kind: "error" });
    }
    return;
  }

  // ストリーム読み取り — streamRecordDraft (FE-008) と同じパターン
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  /**
   * SSE フレームを解析してコールバックを呼び出す。
   * フレームは `\n\n` で区切られ、各行は `event:` または `data:` で始まる。
   * BE-017 フレーム形式:
   *   チャンク:  data: {"text":"...","chunk_index":N,"chunk_count":M,"done":false}\n\n
   *   完了:      event: complete\ndata: {"full_text":"...","duration_seconds":...,"chunk_count":M}\n\n
   *   エラー:    event: error\ndata: {"code":"...","chunk_index":N}\n\n
   */
  function processFrames(raw: string): void {
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

      let parsed: unknown;
      try {
        parsed = JSON.parse(dataLine) as unknown;
      } catch {
        continue;
      }

      // 非オブジェクト値は不正フレームとしてスキップ (FE-011 isJsonObject パターン)
      if (!isJsonObject(parsed)) continue;
      const p = parsed;

      if (eventType === "complete") {
        // 完了フレーム: { full_text, duration_seconds, chunk_count }
        const fullText = typeof p["full_text"] === "string" ? p["full_text"] : "";
        const durationSeconds =
          typeof p["duration_seconds"] === "number" ? p["duration_seconds"] : null;
        const chunkCount = typeof p["chunk_count"] === "number" ? p["chunk_count"] : 0;
        opts.onComplete({ fullText, durationSeconds, chunkCount });
      } else if (eventType === "error") {
        // エラーフレーム: { code, chunk_index }
        const code = typeof p["code"] === "string" ? p["code"] : "";
        const chunkIndex = typeof p["chunk_index"] === "number" ? p["chunk_index"] : undefined;
        let kind: TranscribeStreamErrorKind;
        switch (code) {
          case "encounter_not_found":
            kind = "encounter_not_found";
            break;
          case "validation_error":
            kind = "validation_error";
            break;
          case "unsupported_format":
            kind = "unsupported_format";
            break;
          case "transcription_unavailable":
            kind = "transcription_unavailable";
            break;
          case "transcription_timeout":
            kind = "transcription_timeout";
            break;
          default:
            kind = "error";
        }
        opts.onError({ kind, chunkIndex });
      } else {
        // チャンクフレーム: { text, chunk_index, chunk_count, done }
        const text = typeof p["text"] === "string" ? p["text"] : "";
        const chunkIndex = typeof p["chunk_index"] === "number" ? p["chunk_index"] : 0;
        const chunkCount = typeof p["chunk_count"] === "number" ? p["chunk_count"] : 0;
        // PHI: テキストを console.* に出力しない
        if (text !== "") {
          opts.onChunk(text, chunkIndex, chunkCount);
        }
      }
    }
  }

  try {
    while (true) {
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
    // AbortError はキャンセルの正常系 — 呼び出し元に伝播させる
    if (err instanceof DOMException && err.name === "AbortError") {
      throw err;
    }
    opts.onError({ kind: "error" });
  }
}
