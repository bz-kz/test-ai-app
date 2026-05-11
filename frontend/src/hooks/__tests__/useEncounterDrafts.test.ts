import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useEncounterDrafts } from "../useEncounterDrafts";

// サービス層をモック — 実際の fetch は呼び出さない
vi.mock("@/services/drafts", () => ({
  listDraftsByEncounter: vi.fn(),
}));

import { listDraftsByEncounter } from "@/services/drafts";

const mockList = vi.mocked(listDraftsByEncounter);

const FAKE_ENCOUNTER_ID = "00000000-0000-0000-0000-000000000010";

const FAKE_DRAFT_1 = {
  id: "00000000-0000-0000-0000-000000000021",
  encounter_id: FAKE_ENCOUNTER_ID,
  content: "S: 最新の下書き。",
  confidence: 0.85,
  created_at: "2024-01-02T00:00:00Z",
  updated_at: "2024-01-02T00:00:00Z",
};

const FAKE_DRAFT_2 = {
  id: "00000000-0000-0000-0000-000000000022",
  encounter_id: FAKE_ENCOUNTER_ID,
  content: "S: 古い下書き。",
  confidence: 0.7,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

describe("useEncounterDrafts", () => {
  beforeEach(() => {
    mockList.mockReset();
  });

  it("初期状態は status=idle, drafts=[], latest=null, error=null", () => {
    const { result } = renderHook(() => useEncounterDrafts());
    expect(result.current.status).toBe("idle");
    expect(result.current.drafts).toEqual([]);
    expect(result.current.latest).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("load() 呼び出し直後は status=loading になる", () => {
    // 永遠に pending (解決されない)
    mockList.mockImplementation(() => new Promise<never>(() => undefined));

    const { result } = renderHook(() => useEncounterDrafts());

    act(() => {
      result.current.load(FAKE_ENCOUNTER_ID);
    });

    expect(result.current.status).toBe("loading");
  });

  it("成功 (下書きあり): status=loaded, drafts と latest が設定される (DESC 順維持)", async () => {
    // バックエンドが DESC 順で返すためフロントはそのまま保持する
    mockList.mockResolvedValueOnce({ kind: "found", drafts: [FAKE_DRAFT_1, FAKE_DRAFT_2] });

    const { result } = renderHook(() => useEncounterDrafts());

    await act(async () => {
      result.current.load(FAKE_ENCOUNTER_ID);
      await Promise.resolve();
    });

    expect(result.current.status).toBe("loaded");
    expect(result.current.drafts).toEqual([FAKE_DRAFT_1, FAKE_DRAFT_2]);
    // latest は先頭 (最新) の下書き
    expect(result.current.latest).toEqual(FAKE_DRAFT_1);
    expect(result.current.error).toBeNull();
  });

  it("成功 (空リスト): status=loaded, drafts=[], latest=null", async () => {
    mockList.mockResolvedValueOnce({ kind: "found", drafts: [] });

    const { result } = renderHook(() => useEncounterDrafts());

    await act(async () => {
      result.current.load(FAKE_ENCOUNTER_ID);
      await Promise.resolve();
    });

    expect(result.current.status).toBe("loaded");
    expect(result.current.drafts).toEqual([]);
    expect(result.current.latest).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("エラー時: status=error と日本語エラーメッセージが設定される", async () => {
    mockList.mockResolvedValueOnce({ kind: "error" });

    const { result } = renderHook(() => useEncounterDrafts());

    await act(async () => {
      result.current.load(FAKE_ENCOUNTER_ID);
      await Promise.resolve();
    });

    expect(result.current.status).toBe("error");
    expect(result.current.error).toMatch(/エラーが発生しました/);
    expect(result.current.latest).toBeNull();
  });

  it("load() の多重呼び出し: 前のリクエストがキャンセルされて最後の結果が使われる", async () => {
    const firstDraft = { ...FAKE_DRAFT_2, id: "first" };
    const secondDraft = { ...FAKE_DRAFT_1, id: "second" };

    // 1 回目のリクエストは abort されるため、AbortError を throw させる
    let firstAbortController: AbortController | null = null;
    mockList.mockImplementationOnce((_, opts) => {
      // abort signal を保持して後でキャンセルできるようにする
      return new Promise((resolve, reject) => {
        if (opts?.signal) {
          opts.signal.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"));
          });
        }
        // 1 回目はすぐに解決しない (abort されるまで pending)
        firstAbortController = new AbortController();
        void firstAbortController;
        // ここでは resolve を呼ばないため pending のまま
      });
    });
    // 2 回目のリクエストは即座に解決する
    mockList.mockResolvedValueOnce({ kind: "found", drafts: [secondDraft] });

    const { result } = renderHook(() => useEncounterDrafts());

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
    expect(result.current.drafts).toEqual([secondDraft]);
    expect(result.current.latest).toEqual(secondDraft);

    // firstAbortController は使われないので void する
    void firstDraft;
  });

  it("成功 (単一下書き): latest が唯一の下書きを指す", async () => {
    mockList.mockResolvedValueOnce({ kind: "found", drafts: [FAKE_DRAFT_1] });

    const { result } = renderHook(() => useEncounterDrafts());

    await act(async () => {
      result.current.load(FAKE_ENCOUNTER_ID);
      await Promise.resolve();
    });

    expect(result.current.status).toBe("loaded");
    expect(result.current.latest).toEqual(FAKE_DRAFT_1);
  });

  it("network_error は service が kind=error を返すため status=error になる", async () => {
    mockList.mockResolvedValueOnce({ kind: "error" });

    const { result } = renderHook(() => useEncounterDrafts());

    await act(async () => {
      result.current.load(FAKE_ENCOUNTER_ID);
      await Promise.resolve();
    });

    expect(result.current.status).toBe("error");
    expect(result.current.error).not.toBeNull();
  });
});
