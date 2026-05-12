import { describe, it, expect, vi, beforeEach } from "vitest";
import { transcribeAudio } from "../asr";
import { API_BASE_URL, CLINICIAN_ID } from "@/lib/constants";

// fetch をグローバルモック
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

const FAKE_ENCOUNTER_ID = "00000000-0000-0000-0000-000000000099";
const FAKE_AUDIO = new Blob(["audio-bytes"], { type: "audio/webm;codecs=opus" });

/** Response モックヘルパー */
function makeResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

/** ネットワーク障害 (fetch が throw する) ヘルパー */
function makeNetworkError(): Error {
  return new TypeError("Failed to fetch");
}

describe("transcribeAudio", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  // --- リクエスト構造検証 ---

  it("正しい URL / メソッド / ヘッダー / FormData で fetch を呼び出す", async () => {
    mockFetch.mockResolvedValueOnce(makeResponse(200, { text: "テスト", duration_ms: 1234 }));
    await transcribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO);

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit];

    // URL に encounterId が含まれている
    expect(url).toBe(`${API_BASE_URL}/encounters/${FAKE_ENCOUNTER_ID}/transcribe`);
    expect(init.method).toBe("POST");
    // X-Clinician-Id ヘッダー
    expect((init.headers as Record<string, string>)["X-Clinician-Id"]).toBe(CLINICIAN_ID);
    // body は FormData
    expect(init.body).toBeInstanceOf(FormData);
    const fd = init.body as FormData;
    expect(fd.get("audio")).not.toBeNull();
  });

  it("encounterId が URL エンコードされる", async () => {
    const encodedId = "encounter/with/slashes";
    mockFetch.mockResolvedValueOnce(makeResponse(200, { text: "" }));
    await transcribeAudio(encodedId, FAKE_AUDIO);
    const [url] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toContain(encodeURIComponent(encodedId));
  });

  // --- 成功 (200) ---

  it("200: kind=success、text と durationMs が設定される", async () => {
    mockFetch.mockResolvedValueOnce(makeResponse(200, { text: "あ", duration_ms: 1234 }));
    const result = await transcribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO);
    expect(result).toEqual({ kind: "success", text: "あ", durationMs: 1234 });
  });

  it("200 で duration_ms がない場合: durationMs=undefined", async () => {
    mockFetch.mockResolvedValueOnce(makeResponse(200, { text: "テスト" }));
    const result = await transcribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO);
    expect(result).toEqual({ kind: "success", text: "テスト", durationMs: undefined });
  });

  // --- エラー系 ---

  it("404: kind=encounter_not_found", async () => {
    mockFetch.mockResolvedValueOnce(makeResponse(404, {}));
    const result = await transcribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO);
    expect(result).toEqual({ kind: "encounter_not_found" });
  });

  it("415: kind=unsupported_format", async () => {
    mockFetch.mockResolvedValueOnce(makeResponse(415, {}));
    const result = await transcribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO);
    expect(result).toEqual({ kind: "unsupported_format" });
  });

  it("422 FastAPI 形式: kind=validation_error、fields に loc 末尾が入る", async () => {
    const detail = [
      { loc: ["body", "audio"], msg: "field required" },
      { loc: ["body", "encounter_id"], msg: "invalid uuid" },
    ];
    mockFetch.mockResolvedValueOnce(makeResponse(422, { detail }));
    const result = await transcribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO);
    expect(result).toEqual({ kind: "validation_error", fields: ["audio", "encounter_id"] });
  });

  it("422 で detail が文字列の場合: fields=[]", async () => {
    mockFetch.mockResolvedValueOnce(makeResponse(422, { detail: "invalid" }));
    const result = await transcribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO);
    expect(result).toEqual({ kind: "validation_error", fields: [] });
  });

  it("503: kind=transcription_unavailable", async () => {
    mockFetch.mockResolvedValueOnce(makeResponse(503, {}));
    const result = await transcribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO);
    expect(result).toEqual({ kind: "transcription_unavailable" });
  });

  it("504: kind=transcription_timeout", async () => {
    mockFetch.mockResolvedValueOnce(makeResponse(504, {}));
    const result = await transcribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO);
    expect(result).toEqual({ kind: "transcription_timeout" });
  });

  it("その他のステータス (500): kind=error", async () => {
    mockFetch.mockResolvedValueOnce(makeResponse(500, {}));
    const result = await transcribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO);
    expect(result).toEqual({ kind: "error" });
  });

  it("ネットワークエラー (fetch が throw): kind=error", async () => {
    mockFetch.mockRejectedValueOnce(makeNetworkError());
    const result = await transcribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO);
    expect(result).toEqual({ kind: "error" });
  });

  it("AbortError は再スローされる", async () => {
    const abortError = new DOMException("aborted", "AbortError");
    mockFetch.mockRejectedValueOnce(abortError);
    await expect(transcribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO)).rejects.toThrow("aborted");
  });

  it("AbortSignal を渡すと fetch の signal に転送される", async () => {
    mockFetch.mockResolvedValueOnce(makeResponse(200, { text: "" }));
    const controller = new AbortController();
    await transcribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO, { signal: controller.signal });
    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(init.signal).toBe(controller.signal);
  });
});
