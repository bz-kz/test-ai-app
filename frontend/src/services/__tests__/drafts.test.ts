import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  createRecordDraft,
  editRecordDraft,
  finalizeRecordDraft,
  getRecordFinalById,
  listDraftsByEncounter,
} from "../drafts";

// apiFetch をモック — 実際の fetch は呼び出さない
vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from "@/lib/api";

const mockApiFetch = vi.mocked(apiFetch);

const FAKE_ENCOUNTER_ID = "00000000-0000-0000-0000-000000000010";
const FAKE_DRAFT_ID = "00000000-0000-0000-0000-000000000020";
const FAKE_FINAL_ID = "00000000-0000-0000-0000-000000000030";
const FAKE_CLINICIAN_ID = "00000000-0000-0000-0000-000000000001";

const FAKE_DRAFT = {
  id: FAKE_DRAFT_ID,
  encounter_id: FAKE_ENCOUNTER_ID,
  content: "S: 頭痛。\nO: 正常。\nA: 緊張性頭痛。\nP: 経過観察。",
  confidence: 0.85,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

const FAKE_FINAL = {
  id: FAKE_FINAL_ID,
  encounter_id: FAKE_ENCOUNTER_ID,
  content: "S: 頭痛。\nO: 正常。\nA: 緊張性頭痛。\nP: 経過観察。",
  confidence: 0.85,
  clinician_id: FAKE_CLINICIAN_ID,
  predecessor_id: null,
  created_at: "2024-01-01T00:00:00Z",
};

describe("createRecordDraft", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it("成功時: kind=created を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: FAKE_DRAFT });
    const result = await createRecordDraft(FAKE_ENCOUNTER_ID, "頭痛の訴え");
    expect(result).toEqual({ kind: "created", draft: FAKE_DRAFT });
  });

  it("404: kind=encounter_not_found を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "not_found" });
    const result = await createRecordDraft(FAKE_ENCOUNTER_ID, "入力");
    expect(result).toEqual({ kind: "encounter_not_found" });
  });
});

describe("editRecordDraft", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it("成功時: kind=updated を返す", async () => {
    const updatedDraft = { ...FAKE_DRAFT, content: "更新後の内容" };
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: updatedDraft });
    const result = await editRecordDraft(FAKE_DRAFT_ID, "更新後の内容", FAKE_CLINICIAN_ID);
    expect(result).toEqual({ kind: "updated", draft: updatedDraft });
  });

  it("404: kind=draft_not_found を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "not_found" });
    const result = await editRecordDraft(FAKE_DRAFT_ID, "内容", FAKE_CLINICIAN_ID);
    expect(result).toEqual({ kind: "draft_not_found" });
  });

  it("422: kind=validation_error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "validation_error", fields: ["content"] });
    const result = await editRecordDraft(FAKE_DRAFT_ID, "", FAKE_CLINICIAN_ID);
    expect(result).toEqual({ kind: "validation_error", fields: ["content"] });
  });

  it("server_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "server_error", code: "500" });
    const result = await editRecordDraft(FAKE_DRAFT_ID, "内容", FAKE_CLINICIAN_ID);
    expect(result).toEqual({ kind: "error" });
  });

  it("network_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "network_error" });
    const result = await editRecordDraft(FAKE_DRAFT_ID, "内容", FAKE_CLINICIAN_ID);
    expect(result).toEqual({ kind: "error" });
  });

  it("PATCH メソッドと正しいパスで apiFetch を呼び出す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: FAKE_DRAFT });
    await editRecordDraft(FAKE_DRAFT_ID, "内容", FAKE_CLINICIAN_ID);
    expect(mockApiFetch).toHaveBeenCalledWith(
      `/drafts/${FAKE_DRAFT_ID}`,
      expect.objectContaining({ method: "PATCH" })
    );
  });
});

describe("finalizeRecordDraft", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it("成功時: kind=finalized を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: FAKE_FINAL });
    const result = await finalizeRecordDraft(FAKE_DRAFT_ID, FAKE_CLINICIAN_ID);
    expect(result).toEqual({ kind: "finalized", final: FAKE_FINAL });
  });

  it("404: kind=draft_not_found を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "not_found" });
    const result = await finalizeRecordDraft(FAKE_DRAFT_ID, FAKE_CLINICIAN_ID);
    expect(result).toEqual({ kind: "draft_not_found" });
  });

  it("409 (encounter_already_finalized): kind=encounter_already_finalized を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({
      kind: "server_error",
      code: "encounter_already_finalized",
    });
    const result = await finalizeRecordDraft(FAKE_DRAFT_ID, FAKE_CLINICIAN_ID);
    expect(result).toEqual({ kind: "encounter_already_finalized" });
  });

  it("server_error (その他): kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "server_error", code: "500" });
    const result = await finalizeRecordDraft(FAKE_DRAFT_ID, FAKE_CLINICIAN_ID);
    expect(result).toEqual({ kind: "error" });
  });

  it("network_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "network_error" });
    const result = await finalizeRecordDraft(FAKE_DRAFT_ID, FAKE_CLINICIAN_ID);
    expect(result).toEqual({ kind: "error" });
  });

  it("POST メソッドと正しいパスで apiFetch を呼び出す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: FAKE_FINAL });
    await finalizeRecordDraft(FAKE_DRAFT_ID, FAKE_CLINICIAN_ID);
    expect(mockApiFetch).toHaveBeenCalledWith(
      `/drafts/${FAKE_DRAFT_ID}/finalize`,
      expect.objectContaining({ method: "POST" })
    );
  });
});

describe("listDraftsByEncounter", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it("成功時 (単一下書き): kind=found と drafts 配列を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: [FAKE_DRAFT] });
    const result = await listDraftsByEncounter(FAKE_ENCOUNTER_ID);
    expect(result).toEqual({ kind: "found", drafts: [FAKE_DRAFT] });
  });

  it("成功時 (複数下書き): DESC 順が保持される", async () => {
    const olderDraft = { ...FAKE_DRAFT, id: "older", created_at: "2024-01-01T00:00:00Z" };
    const newerDraft = { ...FAKE_DRAFT, id: "newer", created_at: "2024-01-02T00:00:00Z" };
    // バックエンドが DESC 順で返すため、フロントエンドはそのまま返す
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: [newerDraft, olderDraft] });
    const result = await listDraftsByEncounter(FAKE_ENCOUNTER_ID);
    expect(result).toEqual({ kind: "found", drafts: [newerDraft, olderDraft] });
  });

  it("成功時 (空リスト): kind=found と空配列を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: [] });
    const result = await listDraftsByEncounter(FAKE_ENCOUNTER_ID);
    expect(result).toEqual({ kind: "found", drafts: [] });
  });

  it("server_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "server_error", code: "500" });
    const result = await listDraftsByEncounter(FAKE_ENCOUNTER_ID);
    expect(result).toEqual({ kind: "error" });
  });

  it("network_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "network_error" });
    const result = await listDraftsByEncounter(FAKE_ENCOUNTER_ID);
    expect(result).toEqual({ kind: "error" });
  });

  it("GET メソッドと正しいパスで apiFetch を呼び出す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: [] });
    await listDraftsByEncounter(FAKE_ENCOUNTER_ID);
    expect(mockApiFetch).toHaveBeenCalledWith(
      `/encounters/${FAKE_ENCOUNTER_ID}/drafts`,
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
