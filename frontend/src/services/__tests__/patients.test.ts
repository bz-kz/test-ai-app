import { describe, it, expect, vi, beforeEach } from "vitest";
import { searchPatientsByMrn, getPatientById } from "../patients";

// apiFetch をモック — 実際の fetch は呼び出さない
vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from "@/lib/api";

const mockApiFetch = vi.mocked(apiFetch);

const FAKE_PATIENT_ID = "00000000-0000-0000-0000-000000000001";

const FAKE_PATIENT = {
  id: FAKE_PATIENT_ID,
  mrn: "MRN-TEST-001",
  family_name: "山田",
  given_name: "太郎",
  date_of_birth: "1990-01-01",
  created_at: "2024-01-01T00:00:00Z",
};

describe("searchPatientsByMrn", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it("成功時: kind=found と patient を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: FAKE_PATIENT });
    const result = await searchPatientsByMrn("MRN-TEST-001");
    expect(result).toEqual({ kind: "found", patient: FAKE_PATIENT });
  });

  it("404: kind=not_found を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "not_found" });
    const result = await searchPatientsByMrn("MRN-UNKNOWN");
    expect(result).toEqual({ kind: "not_found" });
  });

  it("server_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "server_error", code: "500" });
    const result = await searchPatientsByMrn("MRN-TEST-001");
    expect(result).toEqual({ kind: "error" });
  });

  it("network_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "network_error" });
    const result = await searchPatientsByMrn("MRN-TEST-001");
    expect(result).toEqual({ kind: "error" });
  });
});

describe("getPatientById", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it("成功時: kind=found と patient を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: FAKE_PATIENT });
    const result = await getPatientById(FAKE_PATIENT_ID);
    expect(result).toEqual({ kind: "found", patient: FAKE_PATIENT });
  });

  it("404: kind=not_found を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "not_found" });
    const result = await getPatientById(FAKE_PATIENT_ID);
    expect(result).toEqual({ kind: "not_found" });
  });

  it("server_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "server_error", code: "500" });
    const result = await getPatientById(FAKE_PATIENT_ID);
    expect(result).toEqual({ kind: "error" });
  });

  it("network_error: kind=error を返す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "network_error" });
    const result = await getPatientById(FAKE_PATIENT_ID);
    expect(result).toEqual({ kind: "error" });
  });

  it("正しいパスで apiFetch を呼び出す", async () => {
    mockApiFetch.mockResolvedValueOnce({ kind: "ok", data: FAKE_PATIENT });
    await getPatientById(FAKE_PATIENT_ID);
    expect(mockApiFetch).toHaveBeenCalledWith(`/patients/${FAKE_PATIENT_ID}`, expect.anything());
  });
});
