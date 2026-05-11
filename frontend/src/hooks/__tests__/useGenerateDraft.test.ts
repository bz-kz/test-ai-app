import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useGenerateDraft } from "../useGenerateDraft";

// サービス層をモック — 実際の fetch は呼び出さない
vi.mock("@/services/drafts", () => ({
  createRecordDraft: vi.fn(),
}));

import { createRecordDraft } from "@/services/drafts";

const mockCreate = vi.mocked(createRecordDraft);

const FAKE_ENCOUNTER_ID = "00000000-0000-0000-0000-000000000010";

const FAKE_DRAFT = {
  id: "00000000-0000-0000-0000-000000000020",
  encounter_id: FAKE_ENCOUNTER_ID,
  content: "S: 患者は頭痛を訴えている。\nO: バイタル正常。\nA: 緊張性頭痛疑い。\nP: 経過観察。",
  confidence: 0.85,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

describe("useGenerateDraft", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockCreate.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("初期状態は idle で draft は null", () => {
    const { result } = renderHook(() => useGenerateDraft(FAKE_ENCOUNTER_ID));
    expect(result.current.status).toBe("idle");
    expect(result.current.draft).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.elapsedMs).toBe(0);
  });

  it("generate 呼び出し後に status が generating に遷移する", async () => {
    // サービスが永遠に pending のまま (キャンセルされるまで)
    mockCreate.mockImplementation(() => new Promise<never>(() => undefined));

    const { result } = renderHook(() => useGenerateDraft(FAKE_ENCOUNTER_ID));

    act(() => {
      result.current.setClinicalInput("頭痛が続いている");
    });

    act(() => {
      result.current.generate();
    });

    expect(result.current.status).toBe("generating");
  });

  it("generate 成功: status が success になり draft が設定される", async () => {
    mockCreate.mockResolvedValueOnce({ kind: "created", draft: FAKE_DRAFT });

    const { result } = renderHook(() => useGenerateDraft(FAKE_ENCOUNTER_ID));

    act(() => {
      result.current.setClinicalInput("頭痛が続いている");
    });

    await act(async () => {
      result.current.generate();
      await Promise.resolve();
    });

    expect(result.current.status).toBe("success");
    expect(result.current.draft).toEqual(FAKE_DRAFT);
    expect(result.current.error).toBeNull();
  });

  it("encounter_not_found: status が encounter_not_found になりエラーメッセージが設定される", async () => {
    mockCreate.mockResolvedValueOnce({ kind: "encounter_not_found" });

    const { result } = renderHook(() => useGenerateDraft(FAKE_ENCOUNTER_ID));

    act(() => {
      result.current.setClinicalInput("入力");
    });

    await act(async () => {
      result.current.generate();
      await Promise.resolve();
    });

    expect(result.current.status).toBe("encounter_not_found");
    expect(result.current.draft).toBeNull();
    expect(result.current.error).toMatch(/Encounter が見つかりません/);
  });

  it("inference_unavailable: status が inference_unavailable になりエラーメッセージが設定される", async () => {
    mockCreate.mockResolvedValueOnce({ kind: "inference_unavailable" });

    const { result } = renderHook(() => useGenerateDraft(FAKE_ENCOUNTER_ID));

    act(() => {
      result.current.setClinicalInput("入力");
    });

    await act(async () => {
      result.current.generate();
      await Promise.resolve();
    });

    expect(result.current.status).toBe("inference_unavailable");
    expect(result.current.error).toMatch(/推論サービスが一時的に利用できません/);
  });

  it("validation_error: status が error になりエラーメッセージが設定される", async () => {
    mockCreate.mockResolvedValueOnce({ kind: "validation_error", fields: ["clinical_input"] });

    const { result } = renderHook(() => useGenerateDraft(FAKE_ENCOUNTER_ID));

    act(() => {
      result.current.setClinicalInput("入力");
    });

    await act(async () => {
      result.current.generate();
      await Promise.resolve();
    });

    expect(result.current.status).toBe("error");
    expect(result.current.error).toMatch(/下書きの生成に失敗しました/);
  });

  it("cancel: generating 中に cancel() を呼ぶと idle に戻り elapsedMs がリセットされる", async () => {
    // サービスが pending のまま (キャンセルされるまで)
    mockCreate.mockImplementation(() => new Promise<never>(() => undefined));

    const { result } = renderHook(() => useGenerateDraft(FAKE_ENCOUNTER_ID));

    act(() => {
      result.current.setClinicalInput("入力");
    });

    act(() => {
      result.current.generate();
    });

    expect(result.current.status).toBe("generating");

    // 500ms 経過させて elapsedMs が更新されることを確認
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(result.current.elapsedMs).toBeGreaterThan(0);

    act(() => {
      result.current.cancel();
    });

    expect(result.current.status).toBe("idle");
    expect(result.current.elapsedMs).toBe(0);
  });

  it("elapsedMs は generating 中に ~100ms 間隔で増加する", async () => {
    mockCreate.mockImplementation(() => new Promise<never>(() => undefined));

    const { result } = renderHook(() => useGenerateDraft(FAKE_ENCOUNTER_ID));

    act(() => {
      result.current.setClinicalInput("入力");
    });

    act(() => {
      result.current.generate();
    });

    act(() => {
      vi.advanceTimersByTime(300);
    });

    // 300ms 経過後は elapsedMs が増加しているはず (100ms 間隔で 3 回以上更新)
    expect(result.current.elapsedMs).toBeGreaterThanOrEqual(200);

    // クリーンアップ
    act(() => {
      result.current.cancel();
    });
  });

  it("setDraft: 外部から draft を直接置き換えられる", () => {
    const { result } = renderHook(() => useGenerateDraft(FAKE_ENCOUNTER_ID));

    expect(result.current.draft).toBeNull();

    act(() => {
      result.current.setDraft(FAKE_DRAFT);
    });

    expect(result.current.draft).toEqual(FAKE_DRAFT);

    act(() => {
      result.current.setDraft(null);
    });

    expect(result.current.draft).toBeNull();
  });

  it("成功後は elapsedMs が 0 にリセットされる", async () => {
    mockCreate.mockResolvedValueOnce({ kind: "created", draft: FAKE_DRAFT });

    const { result } = renderHook(() => useGenerateDraft(FAKE_ENCOUNTER_ID));

    act(() => {
      result.current.setClinicalInput("入力");
    });

    // タイマーが走る前に即座に解決させる
    await act(async () => {
      result.current.generate();
      await Promise.resolve();
    });

    expect(result.current.status).toBe("success");
    expect(result.current.elapsedMs).toBe(0);
  });
});
