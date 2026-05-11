import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useCreateEncounter } from "../useCreateEncounter";

// サービス層をモック — 実際の fetch は呼び出さない
vi.mock("@/services/encounters", () => ({
  createEncounter: vi.fn(),
}));

import { createEncounter } from "@/services/encounters";

const mockCreate = vi.mocked(createEncounter);

const FAKE_PATIENT_ID = "00000000-0000-0000-0000-000000000001";
const FAKE_ENCOUNTER_ID = "00000000-0000-0000-0000-000000000010";
const FAKE_CLINICIAN_ID = "00000000-0000-0000-0000-000000000001";

const FAKE_ENCOUNTER = {
  id: FAKE_ENCOUNTER_ID,
  patient_id: FAKE_PATIENT_ID,
  encountered_at: "2024-01-15T00:00:00Z",
  clinician_id: FAKE_CLINICIAN_ID,
  created_at: "2024-01-15T09:00:00Z",
};

describe("useCreateEncounter", () => {
  beforeEach(() => {
    mockCreate.mockReset();
  });

  it("初期状態は status=idle, lastCreated=null, error=null", () => {
    const { result } = renderHook(() => useCreateEncounter());
    expect(result.current.status).toBe("idle");
    expect(result.current.lastCreated).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("submit() 呼び出し直後は status=submitting になる", () => {
    // 永遠に pending (解決されない)
    mockCreate.mockImplementation(() => new Promise<never>(() => undefined));

    const { result } = renderHook(() => useCreateEncounter());

    act(() => {
      result.current.submit(FAKE_PATIENT_ID, "2024-01-15");
    });

    expect(result.current.status).toBe("submitting");
  });

  it("成功時: status=success, lastCreated が作成された受診を含む", async () => {
    mockCreate.mockResolvedValueOnce({ kind: "created", encounter: FAKE_ENCOUNTER });

    const { result } = renderHook(() => useCreateEncounter());

    await act(async () => {
      result.current.submit(FAKE_PATIENT_ID, "2024-01-15");
      await Promise.resolve();
    });

    expect(result.current.status).toBe("success");
    expect(result.current.lastCreated).toEqual(FAKE_ENCOUNTER);
    expect(result.current.error).toBeNull();
  });

  it("patient_not_found: status=error と日本語エラーメッセージが設定される", async () => {
    mockCreate.mockResolvedValueOnce({ kind: "patient_not_found" });

    const { result } = renderHook(() => useCreateEncounter());

    await act(async () => {
      result.current.submit(FAKE_PATIENT_ID, "2024-01-15");
      await Promise.resolve();
    });

    expect(result.current.status).toBe("error");
    expect(result.current.error).toMatch(/患者が見つかりません/);
    expect(result.current.lastCreated).toBeNull();
  });

  it("validation_error: status=error と日本語エラーメッセージが設定される", async () => {
    mockCreate.mockResolvedValueOnce({
      kind: "validation_error",
      fields: ["encountered_at"],
    });

    const { result } = renderHook(() => useCreateEncounter());

    await act(async () => {
      result.current.submit(FAKE_PATIENT_ID, "invalid-date");
      await Promise.resolve();
    });

    expect(result.current.status).toBe("error");
    expect(result.current.error).toMatch(/入力内容に誤りがあります/);
  });

  it("error: status=error と日本語エラーメッセージが設定される", async () => {
    mockCreate.mockResolvedValueOnce({ kind: "error" });

    const { result } = renderHook(() => useCreateEncounter());

    await act(async () => {
      result.current.submit(FAKE_PATIENT_ID, "2024-01-15");
      await Promise.resolve();
    });

    expect(result.current.status).toBe("error");
    expect(result.current.error).toMatch(/受診の作成に失敗しました/);
  });

  it("reset() で status=idle, lastCreated=null, error=null にリセットされる", async () => {
    mockCreate.mockResolvedValueOnce({ kind: "created", encounter: FAKE_ENCOUNTER });

    const { result } = renderHook(() => useCreateEncounter());

    await act(async () => {
      result.current.submit(FAKE_PATIENT_ID, "2024-01-15");
      await Promise.resolve();
    });

    expect(result.current.status).toBe("success");

    act(() => {
      result.current.reset();
    });

    expect(result.current.status).toBe("idle");
    expect(result.current.lastCreated).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("submit() の多重呼び出し: 前のリクエストがキャンセルされて最後の結果が使われる", async () => {
    const secondEncounter = { ...FAKE_ENCOUNTER, id: "second-id" };

    // 1 回目のリクエストは abort されるため AbortError を throw させる
    mockCreate.mockImplementationOnce((_, opts) => {
      return new Promise((resolve, reject) => {
        if (opts?.signal) {
          opts.signal.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"));
          });
        }
        // pending のまま (abort されるまで解決しない)
      });
    });
    // 2 回目のリクエストは即座に解決する
    mockCreate.mockResolvedValueOnce({ kind: "created", encounter: secondEncounter });

    const { result } = renderHook(() => useCreateEncounter());

    // 1 回目の submit
    act(() => {
      result.current.submit(FAKE_PATIENT_ID, "2024-01-14");
    });

    // 2 回目の submit (1 回目はキャンセルされる)
    await act(async () => {
      result.current.submit(FAKE_PATIENT_ID, "2024-01-15");
      await Promise.resolve();
    });

    // 最終的には 2 回目の結果が反映される
    expect(result.current.status).toBe("success");
    expect(result.current.lastCreated).toEqual(secondEncounter);
  });
});
