import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  correctRecordFinal,
  getFinalChain,
  getRecordFinalById,
  listFinalsByEncounter,
} from "../finals";

// apiFetch をモック — 実際の fetch は呼び出さない
vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from "@/lib/api";

const mockApiFetch = vi.mocked(apiFetch);

const FAKE_ENCOUNTER_ID = "00000000-0000-0000-0000-000000000010";
const FAKE_FINAL_ID = "00000000-0000-0000-0000-000000000030";
const FAKE_NEW_FINAL_ID = "00000000-0000-0000-0000-000000000031";
const FAKE_CLINICIAN_ID = "00000000-0000-0000-0000-000000000001";

const FAKE_FINAL = {
  id: FAKE_FINAL_ID,
  encounter_id: FAKE_ENCOUNTER_ID,
  content: "S: 頭痛。\nO: 正常。\nA: 緊張性頭痛。\nP: 経過観察。",
  confidence: 0.85,
  clinician_id: FAKE_CLINICIAN_ID,
  predecessor_id: null,
  created_at: "2024-01-01T00:00:00Z",
};

const FAKE_CORRECTED_FINAL = {
  id: FAKE_NEW_FINAL_ID,
  encounter_id: FAKE_ENCOUNTER_ID,
  content: "S: 頭痛 (訂正済み)。\nO: 正常。\nA: 緊張性頭痛。\nP: 経過観察。",
  confidence: null,
  clinician_id: FAKE_CLINICIAN_ID,
  predecessor_id: FAKE_FINAL_ID,
  created_at: "2024-01-02T00:00:00Z",
};

describe("listFinalsByEncounter", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it("成功時: kind=found と finals 配列を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: [FAKE_FINAL] });
    const result = await listFinalsByEncounter(FAKE_ENCOUNTER_ID);
    expect(result).toEqual({ kind: "found", finals: [FAKE_FINAL] });
  });

  it("404: 空の finals リストを kind=found で返す (存在しない受診は空リスト扱い)", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "not_found" });
    const result = await listFinalsByEncounter(FAKE_ENCOUNTER_ID);
    expect(result).toEqual({ kind: "found", finals: [] });
  });

  it("server_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "server_error", code: "500" });
    const result = await listFinalsByEncounter(FAKE_ENCOUNTER_ID);
    expect(result).toEqual({ kind: "error" });
  });
});

describe("correctRecordFinal", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it("成功時: kind=created を返し訂正後の RecordFinal を含む", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: FAKE_CORRECTED_FINAL });
    const result = await correctRecordFinal(FAKE_FINAL_ID, "訂正内容");
    expect(result).toEqual({ kind: "created", final: FAKE_CORRECTED_FINAL });
  });

  it("404: kind=final_not_found を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "not_found" });
    const result = await correctRecordFinal(FAKE_FINAL_ID, "訂正内容");
    expect(result).toEqual({ kind: "final_not_found" });
  });

  it("422: kind=validation_error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "validation_error", fields: ["content"] });
    const result = await correctRecordFinal(FAKE_FINAL_ID, "");
    expect(result).toEqual({ kind: "validation_error", fields: ["content"] });
  });

  it("server_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "server_error", code: "500" });
    const result = await correctRecordFinal(FAKE_FINAL_ID, "訂正内容");
    expect(result).toEqual({ kind: "error" });
  });

  it("network_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "network_error" });
    const result = await correctRecordFinal(FAKE_FINAL_ID, "訂正内容");
    expect(result).toEqual({ kind: "error" });
  });

  it("POST メソッドと正しいパスで apiFetch を呼び出す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: FAKE_CORRECTED_FINAL });
    await correctRecordFinal(FAKE_FINAL_ID, "訂正内容");
    expect(mockApiFetch).toHaveBeenCalledWith(
      `/finals/${FAKE_FINAL_ID}/correct`,
      expect.objectContaining({ method: "POST" })
    );
  });
});

describe("getFinalChain", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it("成功時: kind=found を返し chain 配列を含む", async () => {
    const chain = [FAKE_FINAL, FAKE_CORRECTED_FINAL];
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: chain });
    const result = await getFinalChain(FAKE_FINAL_ID);
    expect(result).toEqual({ kind: "found", chain });
  });

  it("404: kind=not_found を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "not_found" });
    const result = await getFinalChain(FAKE_FINAL_ID);
    expect(result).toEqual({ kind: "not_found" });
  });

  it("server_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "server_error", code: "500" });
    const result = await getFinalChain(FAKE_FINAL_ID);
    expect(result).toEqual({ kind: "error" });
  });

  it("GET メソッドと正しいパスで apiFetch を呼び出す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: [FAKE_FINAL] });
    await getFinalChain(FAKE_FINAL_ID);
    expect(mockApiFetch).toHaveBeenCalledWith(
      `/finals/${FAKE_FINAL_ID}/chain`,
      expect.objectContaining({ method: "GET" })
    );
  });
});

describe("getRecordFinalById", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it("成功時: kind=found を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: FAKE_FINAL });
    const result = await getRecordFinalById(FAKE_FINAL_ID);
    expect(result).toEqual({ kind: "found", final: FAKE_FINAL });
  });

  it("404: kind=not_found を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "not_found" });
    const result = await getRecordFinalById(FAKE_FINAL_ID);
    expect(result).toEqual({ kind: "not_found" });
  });

  it("server_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "server_error", code: "500" });
    const result = await getRecordFinalById(FAKE_FINAL_ID);
    expect(result).toEqual({ kind: "error" });
  });

  it("network_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "network_error" });
    const result = await getRecordFinalById(FAKE_FINAL_ID);
    expect(result).toEqual({ kind: "error" });
  });
});
