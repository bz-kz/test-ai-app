/**
 * 音声文字起こしサービス層。
 *
 * multipart/form-data で音声 Blob を POST /encounters/{id}/transcribe に送信する。
 * apiFetch は Content-Type を自動設定するため、multipart には生 fetch を使う
 * (apiFetch が JSON Content-Type を強制するため、FormData との互換性がない)。
 * この例外は drafts.ts:272 の SSE raw-fetch 先例と同じ理由による。
 *
 * PHI ルール (local-llm-and-phi.md §3):
 * - 音声 Blob、文字起こしテキスト、encounterId を console.* に出力しない。
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
