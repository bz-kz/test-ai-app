import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useFinalChain } from "../useFinalChain";

// サービス層をモック — 実際の fetch は呼び出さない
vi.mock("@/services/finals", () => ({
  getFinalChain: vi.fn(),
  correctRecordFinal: vi.fn(),
}));

import { getFinalChain } from "@/services/finals";

const mockGetChain = vi.mocked(getFinalChain);

const FAKE_ENCOUNTER_ID = "00000000-0000-0000-0000-000000000010";
const FAKE_FINAL_ID = "00000000-0000-0000-0000-000000000030";
const FAKE_CLINICIAN_ID = "00000000-0000-0000-0000-000000000001";

const FAKE_FINAL_V1 = {
  id: "00000000-0000-0000-0000-000000000031",
  encounter_id: FAKE_ENCOUNTER_ID,
  content: "S: 最初の確定カルテ。",
  confidence: 0.85,
  clinician_id: FAKE_CLINICIAN_ID,
  predecessor_id: null,
  created_at: "2024-01-01T00:00:00Z",
};

const FAKE_FINAL_V2 = {
  id: FAKE_FINAL_ID,
  encounter_id: FAKE_ENCOUNTER_ID,
  content: "S: 訂正後の確定カルテ。",
  confidence: null,
  clinician_id: FAKE_CLINICIAN_ID,
  predecessor_id: FAKE_FINAL_V1.id,
  created_at: "2024-01-02T00:00:00Z",
};

describe("useFinalChain", () => {
  beforeEach(() => {
    mockGetChain.mockReset();
  });

  it("初期状態は status=idle, chain=[], error=null", () => {
    const { result } = renderHook(() => useFinalChain());
    expect(result.current.status).toBe("idle");
    expect(result.current.chain).toEqual([]);
    expect(result.current.error).toBeNull();
  });

  it("load() 呼び出し直後は status=loading になる", () => {
    // 永遠に pending (解決されない)
    mockGetChain.mockImplementation(() => new Promise<never>(() => undefined));

    const { result } = renderHook(() => useFinalChain());

    act(() => {
      result.current.load(FAKE_FINAL_ID);
    });

    expect(result.current.status).toBe("loading");
  });

  it("成功 (chain length ≥ 2): status=loaded, chain が oldest→newest 順で設定される", async () => {
    // バックエンドは oldest → newest 順で返す (BE-008 契約)
    mockGetChain.mockResolvedValueOnce({ kind: "found", chain: [FAKE_FINAL_V1, FAKE_FINAL_V2] });

    const { result } = renderHook(() => useFinalChain());

    await act(async () => {
      result.current.load(FAKE_FINAL_ID);
      await Promise.resolve();
    });

    expect(result.current.status).toBe("loaded");
    expect(result.current.chain).toHaveLength(2);
    // oldest が先頭
    expect(result.current.chain[0]).toEqual(FAKE_FINAL_V1);
    // newest が末尾
    expect(result.current.chain[1]).toEqual(FAKE_FINAL_V2);
    expect(result.current.error).toBeNull();
  });

  it("not_found: status=not_found と日本語エラーメッセージが設定される", async () => {
    mockGetChain.mockResolvedValueOnce({ kind: "not_found" });

    const { result } = renderHook(() => useFinalChain());

    await act(async () => {
      result.current.load("bogus-final-id");
      await Promise.resolve();
    });

    expect(result.current.status).toBe("not_found");
    expect(result.current.chain).toEqual([]);
    expect(result.current.error).toMatch(/確定カルテが見つかりません/);
  });

  it("エラー時: status=error と日本語エラーメッセージが設定される", async () => {
    mockGetChain.mockResolvedValueOnce({ kind: "error" });

    const { result } = renderHook(() => useFinalChain());

    await act(async () => {
      result.current.load(FAKE_FINAL_ID);
      await Promise.resolve();
    });

    expect(result.current.status).toBe("error");
    expect(result.current.chain).toEqual([]);
    expect(result.current.error).toMatch(/エラーが発生しました/);
  });

  it("load() の多重呼び出し: 前のリクエストがキャンセルされて最後の結果が使われる", async () => {
    // 1 回目のリクエストは abort されると AbortError を throw する
    mockGetChain.mockImplementationOnce((_, opts) => {
      return new Promise((resolve, reject) => {
        if (opts?.signal) {
          opts.signal.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"));
          });
        }
        // pending のまま (abort されるまで)
      });
    });
    // 2 回目のリクエストは即座に解決する
    mockGetChain.mockResolvedValueOnce({ kind: "found", chain: [FAKE_FINAL_V2] });

    const { result } = renderHook(() => useFinalChain());

    // 1 回目の load
    act(() => {
      result.current.load(FAKE_FINAL_ID);
    });

    // 2 回目の load (1 回目はキャンセルされる)
    await act(async () => {
      result.current.load(FAKE_FINAL_ID);
      await Promise.resolve();
    });

    // 最終的には 2 回目の結果が反映される
    expect(result.current.status).toBe("loaded");
    expect(result.current.chain).toEqual([FAKE_FINAL_V2]);
  });
});
