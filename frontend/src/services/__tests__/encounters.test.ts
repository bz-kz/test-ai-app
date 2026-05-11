import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  listEncountersByPatient,
  getEncounterById,
  createEncounter,
  listFinalsByEncounter,
} from "../encounters";

// apiFetch をモック — 実際の fetch は呼び出さない
vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from "@/lib/api";

const mockApiFetch = vi.mocked(apiFetch);

const FAKE_PATIENT_ID = "00000000-0000-0000-0000-000000000001";
const FAKE_ENCOUNTER_ID = "00000000-0000-0000-0000-000000000010";
const FAKE_CLINICIAN_ID = "00000000-0000-0000-0000-000000000001";
const FAKE_FINAL_ID = "00000000-0000-0000-0000-000000000030";

const FAKE_ENCOUNTER = {
  id: FAKE_ENCOUNTER_ID,
  patient_id: FAKE_PATIENT_ID,
  encountered_at: "2024-01-15T09:00:00Z",
  clinician_id: FAKE_CLINICIAN_ID,
  created_at: "2024-01-15T09:00:00Z",
};

const FAKE_FINAL = {
  id: FAKE_FINAL_ID,
  encounter_id: FAKE_ENCOUNTER_ID,
  content: "S: 頭痛。\nO: 正常。\nA: 緊張性頭痛。\nP: 経過観察。",
  confidence: 0.85,
  clinician_id: FAKE_CLINICIAN_ID,
  predecessor_id: null,
  created_at: "2024-01-15T10:00:00Z",
};

describe("listEncountersByPatient", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it("成功時: kind=found と encounters 配列を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: [FAKE_ENCOUNTER] });
    const result = await listEncountersByPatient(FAKE_PATIENT_ID);
    expect(result).toEqual({ kind: "found", encounters: [FAKE_ENCOUNTER] });
  });

  it("成功 (空): kind=found と空配列を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: [] });
    const result = await listEncountersByPatient(FAKE_PATIENT_ID);
    expect(result).toEqual({ kind: "found", encounters: [] });
  });

  it("404: kind=patient_not_found を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "not_found" });
    const result = await listEncountersByPatient(FAKE_PATIENT_ID);
    expect(result).toEqual({ kind: "patient_not_found" });
  });

  it("server_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "server_error", code: "500" });
    const result = await listEncountersByPatient(FAKE_PATIENT_ID);
    expect(result).toEqual({ kind: "error" });
  });

  it("network_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "network_error" });
    const result = await listEncountersByPatient(FAKE_PATIENT_ID);
    expect(result).toEqual({ kind: "error" });
  });

  it("GET メソッドと正しいパスで apiFetch を呼び出す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: [] });
    await listEncountersByPatient(FAKE_PATIENT_ID);
    expect(mockApiFetch).toHaveBeenCalledWith(
      `/patients/${FAKE_PATIENT_ID}/encounters`,
      expect.not.objectContaining({ method: "POST" })
    );
  });
});

describe("getEncounterById", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it("成功時: kind=found と encounter を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: FAKE_ENCOUNTER });
    const result = await getEncounterById(FAKE_ENCOUNTER_ID);
    expect(result).toEqual({ kind: "found", encounter: FAKE_ENCOUNTER });
  });

  it("404: kind=not_found を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "not_found" });
    const result = await getEncounterById(FAKE_ENCOUNTER_ID);
    expect(result).toEqual({ kind: "not_found" });
  });

  it("server_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "server_error", code: "500" });
    const result = await getEncounterById(FAKE_ENCOUNTER_ID);
    expect(result).toEqual({ kind: "error" });
  });

  it("network_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "network_error" });
    const result = await getEncounterById(FAKE_ENCOUNTER_ID);
    expect(result).toEqual({ kind: "error" });
  });

  it("正しいパスで apiFetch を呼び出す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: FAKE_ENCOUNTER });
    await getEncounterById(FAKE_ENCOUNTER_ID);
    expect(mockApiFetch).toHaveBeenCalledWith(
      `/encounters/${FAKE_ENCOUNTER_ID}`,
      expect.anything()
    );
  });
});

describe("createEncounter", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it("成功時: kind=created と encounter を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: FAKE_ENCOUNTER });
    const result = await createEncounter({
      patient_id: FAKE_PATIENT_ID,
      encountered_at: "2024-01-15T09:00:00Z",
    });
    expect(result).toEqual({ kind: "created", encounter: FAKE_ENCOUNTER });
  });

  it("404: kind=patient_not_found を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "not_found" });
    const result = await createEncounter({
      patient_id: FAKE_PATIENT_ID,
      encountered_at: "2024-01-15T09:00:00Z",
    });
    expect(result).toEqual({ kind: "patient_not_found" });
  });

  it("422: kind=validation_error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({
      kind: "validation_error",
      fields: ["encountered_at"],
    });
    const result = await createEncounter({
      patient_id: FAKE_PATIENT_ID,
      encountered_at: "invalid",
    });
    expect(result).toEqual({ kind: "validation_error", fields: ["encountered_at"] });
  });

  it("server_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "server_error", code: "500" });
    const result = await createEncounter({
      patient_id: FAKE_PATIENT_ID,
      encountered_at: "2024-01-15T09:00:00Z",
    });
    expect(result).toEqual({ kind: "error" });
  });

  it("network_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "network_error" });
    const result = await createEncounter({
      patient_id: FAKE_PATIENT_ID,
      encountered_at: "2024-01-15T09:00:00Z",
    });
    expect(result).toEqual({ kind: "error" });
  });

  it("POST メソッドと /encounters パスで apiFetch を呼び出す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: FAKE_ENCOUNTER });
    await createEncounter({
      patient_id: FAKE_PATIENT_ID,
      encountered_at: "2024-01-15T09:00:00Z",
    });
    expect(mockApiFetch).toHaveBeenCalledWith(
      "/encounters",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("ボディに clinician_id を含まない (BE-012: X-Clinician-Id ヘッダー経由)", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: FAKE_ENCOUNTER });
    await createEncounter({
      patient_id: FAKE_PATIENT_ID,
      encountered_at: "2024-01-15T09:00:00Z",
    });
    const call = mockApiFetch.mock.calls[0];
    const body = call?.[1]?.body as string | undefined;
    expect(body).toBeDefined();
    const parsed = JSON.parse(body!) as Record<string, unknown>;
    expect(parsed).not.toHaveProperty("clinician_id");
  });
});

describe("listFinalsByEncounter", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it("成功時: kind=found と finals 配列を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: [FAKE_FINAL] });
    const result = await listFinalsByEncounter(FAKE_ENCOUNTER_ID);
    expect(result).toEqual({ kind: "found", finals: [FAKE_FINAL] });
  });

  it("成功 (空): kind=found と空配列を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: [] });
    const result = await listFinalsByEncounter(FAKE_ENCOUNTER_ID);
    expect(result).toEqual({ kind: "found", finals: [] });
  });

  it("server_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "server_error", code: "500" });
    const result = await listFinalsByEncounter(FAKE_ENCOUNTER_ID);
    expect(result).toEqual({ kind: "error" });
  });

  it("network_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "network_error" });
    const result = await listFinalsByEncounter(FAKE_ENCOUNTER_ID);
    expect(result).toEqual({ kind: "error" });
  });

  it("正しいパスで apiFetch を呼び出す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: [] });
    await listFinalsByEncounter(FAKE_ENCOUNTER_ID);
    expect(mockApiFetch).toHaveBeenCalledWith(
      `/encounters/${FAKE_ENCOUNTER_ID}/finals`,
      expect.anything()
    );
  });
});

describe("patients service — getPatientById", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it("モジュールを直接インポートしてテストする必要があるため patients.test.ts に委譲", () => {
    // getPatientById のテストは services/__tests__/patients.test.ts で行う
    expect(true).toBe(true);
  });
});
