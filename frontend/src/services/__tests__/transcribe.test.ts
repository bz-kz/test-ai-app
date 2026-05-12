import { describe, it, expect, vi, beforeEach } from "vitest";
import { transcribeAudio, streamTranscribeAudio } from "../transcribe";
import type { StreamTranscribeOpts } from "../transcribe";
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

// ---------------------------------------------------------------------------
// streamTranscribeAudio テスト (FE-013)
// ---------------------------------------------------------------------------

/**
 * SSE ストリームを模倣する ReadableStream を生成するヘルパー。
 * frames: SSE フレーム文字列の配列 (各要素が \n\n で区切られた 1 フレーム)。
 */
function makeStreamResponse(frames: string[]): Response {
  const body = frames.join("");
  const encoder = new TextEncoder();
  const encoded = encoder.encode(body);

  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(encoded);
      controller.close();
    },
  });

  return {
    ok: true,
    status: 200,
    body: stream,
  } as unknown as Response;
}

/** streamTranscribeAudio 用コールバックモックセット */
function makeCallbacks(): {
  onChunk: ReturnType<typeof vi.fn>;
  onComplete: ReturnType<typeof vi.fn>;
  onError: ReturnType<typeof vi.fn>;
  opts: StreamTranscribeOpts;
} {
  const onChunk = vi.fn();
  const onComplete = vi.fn();
  const onError = vi.fn();
  return {
    onChunk,
    onComplete,
    onError,
    opts: { onChunk, onComplete, onError },
  };
}

describe("streamTranscribeAudio", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("(a) ハッピーパス: 3 チャンク + complete → コールバックが順番に呼ばれる", async () => {
    const frames = [
      `data: ${JSON.stringify({ text: "こんにちは", chunk_index: 0, chunk_count: 3, done: false })}\n\n`,
      `data: ${JSON.stringify({ text: "世界", chunk_index: 1, chunk_count: 3, done: false })}\n\n`,
      `data: ${JSON.stringify({ text: "！", chunk_index: 2, chunk_count: 3, done: false })}\n\n`,
      `event: complete\ndata: ${JSON.stringify({ full_text: "こんにちは世界！", duration_seconds: 1.5, chunk_count: 3 })}\n\n`,
    ];
    mockFetch.mockResolvedValueOnce(makeStreamResponse(frames));

    const { opts, onChunk, onComplete, onError } = makeCallbacks();
    await streamTranscribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO, opts);

    expect(onChunk).toHaveBeenCalledTimes(3);
    expect(onChunk).toHaveBeenNthCalledWith(1, "こんにちは", 0, 3);
    expect(onChunk).toHaveBeenNthCalledWith(2, "世界", 1, 3);
    expect(onChunk).toHaveBeenNthCalledWith(3, "！", 2, 3);
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(onComplete).toHaveBeenCalledWith({
      fullText: "こんにちは世界！",
      durationSeconds: 1.5,
      chunkCount: 3,
    });
    expect(onError).not.toHaveBeenCalled();
  });

  it("(b) 404 同期エラー → onError('encounter_not_found') が呼ばれ、ストリームには入らない", async () => {
    mockFetch.mockResolvedValueOnce(makeResponse(404, {}));
    const { opts, onError, onChunk, onComplete } = makeCallbacks();
    await streamTranscribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO, opts);
    expect(onError).toHaveBeenCalledWith({ kind: "encounter_not_found" });
    expect(onChunk).not.toHaveBeenCalled();
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("(c) 415 同期エラー → onError('unsupported_format')", async () => {
    mockFetch.mockResolvedValueOnce(makeResponse(415, {}));
    const { opts, onError } = makeCallbacks();
    await streamTranscribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO, opts);
    expect(onError).toHaveBeenCalledWith({ kind: "unsupported_format" });
  });

  it("(d) 422 同期エラー → onError('validation_error')", async () => {
    mockFetch.mockResolvedValueOnce(makeResponse(422, {}));
    const { opts, onError } = makeCallbacks();
    await streamTranscribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO, opts);
    expect(onError).toHaveBeenCalledWith({ kind: "validation_error" });
  });

  it("(e) 503 同期エラー → onError('transcription_unavailable')", async () => {
    mockFetch.mockResolvedValueOnce(makeResponse(503, {}));
    const { opts, onError } = makeCallbacks();
    await streamTranscribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO, opts);
    expect(onError).toHaveBeenCalledWith({ kind: "transcription_unavailable" });
  });

  it("(f) ミッドストリーム event:error フレーム (transcription_timeout) → onError が正しい kind で呼ばれる", async () => {
    const frames = [
      `data: ${JSON.stringify({ text: "最初", chunk_index: 0, chunk_count: 3, done: false })}\n\n`,
      `event: error\ndata: ${JSON.stringify({ code: "transcription_timeout", chunk_index: 1 })}\n\n`,
    ];
    mockFetch.mockResolvedValueOnce(makeStreamResponse(frames));
    const { opts, onError, onChunk, onComplete } = makeCallbacks();
    await streamTranscribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO, opts);
    expect(onChunk).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith({ kind: "transcription_timeout", chunkIndex: 1 });
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("(g) AbortError mid-read → 再スローされる", async () => {
    const abortError = new DOMException("aborted", "AbortError");
    mockFetch.mockRejectedValueOnce(abortError);
    const { opts } = makeCallbacks();
    await expect(streamTranscribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO, opts)).rejects.toThrow(
      "aborted"
    );
  });

  it("URL に /transcribe/stream が含まれる", async () => {
    mockFetch.mockResolvedValueOnce(
      makeStreamResponse([
        `event: complete\ndata: ${JSON.stringify({ full_text: "", duration_seconds: null, chunk_count: 0 })}\n\n`,
      ])
    );
    const { opts } = makeCallbacks();
    await streamTranscribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO, opts);
    const [url] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toContain(`/encounters/${FAKE_ENCOUNTER_ID}/transcribe/stream`);
  });

  it("X-Clinician-Id ヘッダーが送られる", async () => {
    mockFetch.mockResolvedValueOnce(
      makeStreamResponse([
        `event: complete\ndata: ${JSON.stringify({ full_text: "", duration_seconds: null, chunk_count: 0 })}\n\n`,
      ])
    );
    const { opts } = makeCallbacks();
    await streamTranscribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO, opts);
    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>)["X-Clinician-Id"]).toBe(CLINICIAN_ID);
  });

  it("body は FormData で audio フィールドを含む", async () => {
    mockFetch.mockResolvedValueOnce(
      makeStreamResponse([
        `event: complete\ndata: ${JSON.stringify({ full_text: "", duration_seconds: null, chunk_count: 0 })}\n\n`,
      ])
    );
    const { opts } = makeCallbacks();
    await streamTranscribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO, opts);
    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(init.body).toBeInstanceOf(FormData);
    const fd = init.body as FormData;
    expect(fd.get("audio")).not.toBeNull();
  });

  it("非オブジェクト data フレーム (数値) は静かにスキップされる", async () => {
    const frames = [
      `data: 42\n\n`,
      `event: complete\ndata: ${JSON.stringify({ full_text: "ok", duration_seconds: null, chunk_count: 0 })}\n\n`,
    ];
    mockFetch.mockResolvedValueOnce(makeStreamResponse(frames));
    const { opts, onChunk, onComplete } = makeCallbacks();
    await streamTranscribeAudio(FAKE_ENCOUNTER_ID, FAKE_AUDIO, opts);
    expect(onChunk).not.toHaveBeenCalled();
    expect(onComplete).toHaveBeenCalledWith({
      fullText: "ok",
      durationSeconds: null,
      chunkCount: 0,
    });
  });
});
