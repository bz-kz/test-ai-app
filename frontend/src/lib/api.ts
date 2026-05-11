/**
 * HTTP クライアントユーティリティ。
 *
 * サービス層がここを経由して API を呼び出す。
 * non-2xx レスポンスは例外ではなく ApiResult の失敗タグに変換する。
 * PHI を含む可能性があるクエリ文字列はログに出力しない。
 *
 * 注: サーバーエラーコンテキストを構造化ログに送るヘルパーは
 * PHI レビュー完了まで導入しない (BE-010)。
 */
import { API_BASE_URL, CLINICIAN_ID } from "@/lib/constants";

/** GET /foo?mrn=X の X はクエリ文字列に PHI が含まれうるため、ログには出さない */
export type ApiResult<T> =
  | { kind: "ok"; data: T }
  | { kind: "not_found" }
  | { kind: "validation_error"; fields: string[] }
  | { kind: "server_error"; code: string }
  | { kind: "network_error" };

/**
 * 型付き fetch ラッパー。
 *
 * - 成功 (2xx): `{ kind: "ok", data: T }` を返す。
 * - 404: `{ kind: "not_found" }` を返す。
 * - 422: `{ kind: "validation_error", fields: [...] }` を返す。
 * - その他 4xx/5xx: `{ kind: "server_error", code }` を返す。
 * - ネットワーク障害: `{ kind: "network_error" }` を返す。
 * - AbortController でキャンセルされた場合のみ例外を再スローする。
 *
 * @param path  `/patients?mrn=X` 形式の相対パス
 * @param init  fetch オプション (signal など)
 */
export async function apiFetch<T>(
  path: string,
  init?: RequestInit & { signal?: AbortSignal }
): Promise<ApiResult<T>> {
  const url = `${API_BASE_URL}${path}`;

  try {
    const response = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        // PoC 用固定 clinician ID — ブラウザストレージには保存しない
        "X-Clinician-Id": CLINICIAN_ID,
        ...init?.headers,
      },
    });

    if (response.ok) {
      const data = (await response.json()) as T;
      return { kind: "ok", data };
    }

    if (response.status === 404) {
      return { kind: "not_found" };
    }

    if (response.status === 422) {
      // FastAPI バリデーションエラーの detail 配列からフィールド名を抽出する
      type ValidationDetail = { loc?: string[]; msg?: string };
      type ValidationBody = { detail?: ValidationDetail[] | string };
      const body = (await response.json().catch(() => ({}))) as ValidationBody;
      const fields: string[] = [];
      if (Array.isArray(body.detail)) {
        for (const item of body.detail) {
          if (item.loc && item.loc.length > 0) {
            fields.push(item.loc[item.loc.length - 1] ?? "unknown");
          }
        }
      }
      return { kind: "validation_error", fields };
    }

    // 予期しないサーバーエラー — コードのみ返す (パス・ボディはログに出さない)
    type ErrorBody = { detail?: { code?: string } | string };
    const body = (await response.json().catch(() => ({}))) as ErrorBody;
    const code =
      typeof body.detail === "object" && body.detail !== null
        ? (body.detail.code ?? String(response.status))
        : String(response.status);
    return { kind: "server_error", code };
  } catch (err) {
    // AbortError はキャンセルの正常系 — 呼び出し元に伝播させる
    if (err instanceof DOMException && err.name === "AbortError") {
      throw err;
    }
    return { kind: "network_error" };
  }
}
