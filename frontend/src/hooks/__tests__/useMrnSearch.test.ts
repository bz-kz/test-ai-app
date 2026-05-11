import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useMrnSearch } from "../useMrnSearch";

// サービス層をモック — 実際の fetch は呼び出さない
vi.mock("@/services/patients", () => ({
  searchPatientsByMrn: vi.fn(),
}));

import { searchPatientsByMrn } from "@/services/patients";

const mockSearch = vi.mocked(searchPatientsByMrn);

const FAKE_PATIENT = {
  id: "00000000-0000-0000-0000-000000000001",
  mrn: "MRN-TEST-001",
  family_name: "山田",
  given_name: "太郎",
  date_of_birth: "1990-01-01",
  created_at: "2024-01-01T00:00:00Z",
};

describe("useMrnSearch", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockSearch.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("初期状態は idle で result は null", () => {
    const { result } = renderHook(() => useMrnSearch());
    expect(result.current.status).toBe("idle");
    expect(result.current.result).toBeNull();
  });

  it("空クエリでは検索を発火しない", async () => {
    const { result } = renderHook(() => useMrnSearch());

    act(() => {
      result.current.setQuery("");
    });

    await act(async () => {
      vi.advanceTimersByTime(300);
    });

    expect(mockSearch).not.toHaveBeenCalled();
    expect(result.current.status).toBe("idle");
  });

  it("200ms 前には検索を発火しない (デバウンス)", async () => {
    const { result } = renderHook(() => useMrnSearch());

    act(() => {
      result.current.setQuery("MRN-001");
    });

    // 100ms 経過 — まだ発火しない
    await act(async () => {
      vi.advanceTimersByTime(100);
    });

    expect(mockSearch).not.toHaveBeenCalled();
  });

  it("200ms 後に検索を発火する", async () => {
    mockSearch.mockResolvedValueOnce({ kind: "found", patient: FAKE_PATIENT });

    const { result } = renderHook(() => useMrnSearch());

    act(() => {
      result.current.setQuery("MRN-001");
    });

    await act(async () => {
      vi.advanceTimersByTime(200);
    });

    expect(mockSearch).toHaveBeenCalledTimes(1);
  });

  it("成功時: searching → found に遷移し result が設定される", async () => {
    mockSearch.mockResolvedValueOnce({ kind: "found", patient: FAKE_PATIENT });

    const { result } = renderHook(() => useMrnSearch());

    act(() => {
      result.current.setQuery("MRN-TEST-001");
    });

    await act(async () => {
      vi.advanceTimersByTime(200);
    });

    // Promise 解決を待つ
    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.status).toBe("found");
    expect(result.current.result).toEqual(FAKE_PATIENT);
  });

  it("not_found 時: searching → not_found に遷移し result は null", async () => {
    mockSearch.mockResolvedValueOnce({ kind: "not_found" });

    const { result } = renderHook(() => useMrnSearch());

    act(() => {
      result.current.setQuery("MRN-UNKNOWN");
    });

    await act(async () => {
      vi.advanceTimersByTime(200);
    });

    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.status).toBe("not_found");
    expect(result.current.result).toBeNull();
  });

  it("error 時: searching → error に遷移し result は null", async () => {
    mockSearch.mockResolvedValueOnce({ kind: "error" });

    const { result } = renderHook(() => useMrnSearch());

    act(() => {
      result.current.setQuery("MRN-ERR");
    });

    await act(async () => {
      vi.advanceTimersByTime(200);
    });

    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.status).toBe("error");
    expect(result.current.result).toBeNull();
  });

  it("クエリ変更時に前のリクエストをキャンセルする", async () => {
    // デバウンス内でクエリが変わると最初のタイマーはクリアされ service は呼ばれない。
    // 2 回目のクエリのみ service が呼ばれ found になることを確認する。
    mockSearch.mockResolvedValueOnce({ kind: "found", patient: FAKE_PATIENT });

    const { result } = renderHook(() => useMrnSearch());

    act(() => {
      result.current.setQuery("MRN-FIRST");
    });

    // 100ms 経過 (デバウンス未完了) の間にクエリを変更
    act(() => {
      vi.advanceTimersByTime(100);
    });

    act(() => {
      result.current.setQuery("MRN-SECOND");
    });

    // 2 回目のクエリのデバウンス 200ms を進める
    await act(async () => {
      vi.advanceTimersByTime(200);
    });

    await act(async () => {
      await Promise.resolve();
    });

    // service は 1 回だけ呼ばれ (最初のクエリはキャンセル済み)、found になる
    expect(mockSearch).toHaveBeenCalledTimes(1);
    expect(result.current.status).toBe("found");
    expect(result.current.result).toEqual(FAKE_PATIENT);
  });
});
