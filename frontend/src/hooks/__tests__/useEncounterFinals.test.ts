import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useEncounterFinals } from "../useEncounterFinals";

// サービス層をモック — 実際の fetch は呼び出さない
vi.mock("@/services/finals", () => ({
  listFinalsByEncounter: vi.fn(),
  correctRecordFinal: vi.fn(),
  getFinalChain: vi.fn(),
}));

import { listFinalsByEncounter } from "@/services/finals";

const mockList = vi.mocked(listFinalsByEncounter);

const FAKE_ENCOUNTER_ID = "00000000-0000-0000-0000-000000000010";
const FAKE_CLINICIAN_ID = "00000000-0000-0000-0000-000000000001";

const FAKE_FINAL_1 = {
  id: "00000000-0000-0000-0000-000000000031",
  encounter_id: FAKE_ENCOUNTER_ID,
  content: "S: 最新の確定カルテ。",
  confidence: 0.9,
  clinician_id: FAKE_CLINICIAN_ID,
  predecessor_id: "00000000-0000-0000-0000-000000000030",
  created_at: "2024-01-02T00:00:00Z",
};

const FAKE_FINAL_2 = {
  id: "00000000-0000-0000-0000-000000000030",
  encounter_id: FAKE_ENCOUNTER_ID,
  content: "S: 古い確定カルテ。",
  confidence: 0.85,
  clinician_id: FAKE_CLINICIAN_ID,
  predecessor_id: null,
  created_at: "2024-01-01T00:00:00Z",
};

describe("useEncounterFinals", () => {
  beforeEach(() => {
    mockList.mockReset();
  });

  it("初期状態は status=idle, finals=[], latest=null, error=null", () => {
    const { result } = renderHook(() => useEncounterFinals());
    expect(result.current.status).toBe("idle");
    expect(result.current.finals).toEqual([]);
    expect(result.current.latest).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("(i) 成功 (確定カルテあり): latest が finals[0] (最新) を指す", async () => {
    // バックエンドが DESC 順で返すためフロントはそのまま保持する
    mockList.mockResolvedValueOnce({ kind: "found", finals: [FAKE_FINAL_1, FAKE_FINAL_2] });

    const { result } = renderHook(() => useEncounterFinals());

    await act(async () => {
      result.current.load(FAKE_ENCOUNTER_ID);
      await Promise.resolve();
    });

    expect(result.current.status).toBe("loaded");
    expect(result.current.finals).toEqual([FAKE_FINAL_1, FAKE_FINAL_2]);
    // latest は先頭 (最新) の確定カルテ
    expect(result.current.latest).toEqual(FAKE_FINAL_1);
    expect(result.current.error).toBeNull();
  });

  it("(ii) 成功 (空リスト): status=loaded, finals=[], latest=null", async () => {
    mockList.mockResolvedValueOnce({ kind: "found", finals: [] });

    const { result } = renderHook(() => useEncounterFinals());

    await act(async () => {
      result.current.load(FAKE_ENCOUNTER_ID);
      await Promise.resolve();
    });

    expect(result.current.status).toBe("loaded");
    expect(result.current.finals).toEqual([]);
    expect(result.current.latest).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("(iii) サービスエラー時: status=error と日本語エラーメッセージが設定される", async () => {
    mockList.mockResolvedValueOnce({ kind: "error" });

    const { result } = renderHook(() => useEncounterFinals());

    await act(async () => {
      result.current.load(FAKE_ENCOUNTER_ID);
      await Promise.resolve();
    });

    expect(result.current.status).toBe("error");
    expect(result.current.error).toMatch(/エラーが発生しました/);
    expect(result.current.latest).toBeNull();
  });

  it("(iv) load() の多重呼び出し: AbortController が前のリクエストをキャンセルし最後の結果が使われる", async () => {
    const firstFinal = { ...FAKE_FINAL_2, id: "first" };
    const secondFinal = { ...FAKE_FINAL_1, id: "second" };

    // 1 回目のリクエストは abort されるまで pending
    mockList.mockImplementationOnce((_, opts) => {
      return new Promise((resolve, reject) => {
        if (opts?.signal) {
          opts.signal.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"));
          });
        }
        // ここでは resolve を呼ばないため pending のまま
        void firstFinal;
      });
    });
    // 2 回目のリクエストは即座に解決する
    mockList.mockResolvedValueOnce({ kind: "found", finals: [secondFinal] });

    const { result } = renderHook(() => useEncounterFinals());

    // 1 回目の load
    act(() => {
      result.current.load(FAKE_ENCOUNTER_ID);
    });

    // 2 回目の load (1 回目はキャンセルされる)
    await act(async () => {
      result.current.load(FAKE_ENCOUNTER_ID);
      await Promise.resolve();
    });

    // 最終的には 2 回目の結果が反映される
    expect(result.current.status).toBe("loaded");
    expect(result.current.finals).toEqual([secondFinal]);
    expect(result.current.latest).toEqual(secondFinal);
  });

  it("(v) AbortError は状態を変更せず無音で飲み込まれる", async () => {
    // AbortError を直接 throw するモック
    mockList.mockImplementationOnce(() => {
      return Promise.reject(new DOMException("Aborted", "AbortError"));
    });

    const { result } = renderHook(() => useEncounterFinals());

    await act(async () => {
      result.current.load(FAKE_ENCOUNTER_ID);
      await Promise.resolve();
    });

    // AbortError は飲み込まれるため loading のまま変わらない
    // (2 回目の load が来るまで loading にとどまる — エラーにならない)
    expect(result.current.status).toBe("loading");
    expect(result.current.error).toBeNull();
  });

  it("load() 呼び出し直後は status=loading になる", () => {
    // 永遠に pending (解決されない)
    mockList.mockImplementation(() => new Promise<never>(() => undefined));

    const { result } = renderHook(() => useEncounterFinals());

    act(() => {
      result.current.load(FAKE_ENCOUNTER_ID);
    });

    expect(result.current.status).toBe("loading");
  });
});
