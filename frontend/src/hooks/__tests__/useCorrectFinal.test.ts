import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useCorrectFinal } from "../useCorrectFinal";

// サービス層をモック — 実際の fetch は呼び出さない
vi.mock("@/services/finals", () => ({
  correctRecordFinal: vi.fn(),
}));

import { correctRecordFinal } from "@/services/finals";

const mockCorrect = vi.mocked(correctRecordFinal);

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

describe("useCorrectFinal", () => {
  beforeEach(() => {
    mockCorrect.mockReset();
  });

  it("初期状態は mode=view, status=idle, error=null, correctedFinal=null", () => {
    const { result } = renderHook(() => useCorrectFinal(FAKE_FINAL, FAKE_CLINICIAN_ID));
    expect(result.current.mode).toBe("view");
    expect(result.current.status).toBe("idle");
    expect(result.current.error).toBeNull();
    expect(result.current.correctedFinal).toBeNull();
  });

  describe("enter", () => {
    it("view → correcting に遷移し、content が sourceFinal.content で初期化される", () => {
      const { result } = renderHook(() => useCorrectFinal(FAKE_FINAL, FAKE_CLINICIAN_ID));
      act(() => {
        result.current.enter();
      });
      expect(result.current.mode).toBe("correcting");
      expect(result.current.content).toBe(FAKE_FINAL.content);
    });

    it("sourceFinal が null のとき enter は何もしない", () => {
      const { result } = renderHook(() => useCorrectFinal(null, FAKE_CLINICIAN_ID));
      act(() => {
        result.current.enter();
      });
      expect(result.current.mode).toBe("view");
    });
  });

  describe("cancel", () => {
    it("correcting → view に戻り、content が空になり status=idle になる", () => {
      const { result } = renderHook(() => useCorrectFinal(FAKE_FINAL, FAKE_CLINICIAN_ID));
      act(() => {
        result.current.enter();
      });
      expect(result.current.mode).toBe("correcting");

      act(() => {
        result.current.cancel();
      });
      expect(result.current.mode).toBe("view");
      expect(result.current.content).toBe("");
      expect(result.current.status).toBe("idle");
      expect(result.current.error).toBeNull();
    });

    it("submitting 中に cancel を呼ぶと mode=view, status=idle に戻る", async () => {
      mockCorrect.mockImplementation(() => new Promise<never>(() => undefined));
      const { result } = renderHook(() => useCorrectFinal(FAKE_FINAL, FAKE_CLINICIAN_ID));

      act(() => {
        result.current.enter();
        result.current.setContent("訂正内容");
      });

      act(() => {
        void result.current.submit();
      });
      expect(result.current.status).toBe("submitting");

      act(() => {
        result.current.cancel();
      });
      expect(result.current.mode).toBe("view");
      expect(result.current.status).toBe("idle");
    });
  });

  describe("submit", () => {
    it("成功時: mode=view に戻り correctedFinal が設定される", async () => {
      mockCorrect.mockResolvedValueOnce({ kind: "created", final: FAKE_CORRECTED_FINAL });

      const { result } = renderHook(() => useCorrectFinal(FAKE_FINAL, FAKE_CLINICIAN_ID));
      act(() => {
        result.current.enter();
        result.current.setContent("訂正後の内容");
      });

      await act(async () => {
        await result.current.submit();
      });

      expect(result.current.mode).toBe("view");
      expect(result.current.correctedFinal).toEqual(FAKE_CORRECTED_FINAL);
      expect(result.current.status).toBe("idle");
      expect(result.current.error).toBeNull();
    });

    it("submit 中は status が submitting になる", () => {
      mockCorrect.mockImplementation(() => new Promise<never>(() => undefined));
      const { result } = renderHook(() => useCorrectFinal(FAKE_FINAL, FAKE_CLINICIAN_ID));

      act(() => {
        result.current.enter();
        result.current.setContent("訂正内容");
      });

      act(() => {
        void result.current.submit();
      });
      expect(result.current.status).toBe("submitting");
    });

    it("final_not_found: status=error と日本語エラーメッセージが設定される", async () => {
      mockCorrect.mockResolvedValueOnce({ kind: "final_not_found" });
      const { result } = renderHook(() => useCorrectFinal(FAKE_FINAL, FAKE_CLINICIAN_ID));
      act(() => {
        result.current.enter();
        result.current.setContent("訂正内容");
      });

      await act(async () => {
        await result.current.submit();
      });

      expect(result.current.status).toBe("error");
      expect(result.current.error).toMatch(/確定カルテが見つかりません/);
      // correcting モードは維持される
      expect(result.current.mode).toBe("correcting");
    });

    it("validation_error: status=error と日本語エラーメッセージが設定される", async () => {
      mockCorrect.mockResolvedValueOnce({ kind: "validation_error", fields: ["content"] });
      const { result } = renderHook(() => useCorrectFinal(FAKE_FINAL, FAKE_CLINICIAN_ID));
      act(() => {
        result.current.enter();
        result.current.setContent("訂正内容");
      });

      await act(async () => {
        await result.current.submit();
      });

      expect(result.current.status).toBe("error");
      expect(result.current.error).toMatch(/入力内容に問題があります/);
    });

    it("error: status=error と汎用エラーメッセージが設定される", async () => {
      mockCorrect.mockResolvedValueOnce({ kind: "error" });
      const { result } = renderHook(() => useCorrectFinal(FAKE_FINAL, FAKE_CLINICIAN_ID));
      act(() => {
        result.current.enter();
        result.current.setContent("訂正内容");
      });

      await act(async () => {
        await result.current.submit();
      });

      expect(result.current.status).toBe("error");
      expect(result.current.error).toMatch(/エラーが発生しました/);
    });

    it("content が空白のみの場合は submit が何もしない", async () => {
      const { result } = renderHook(() => useCorrectFinal(FAKE_FINAL, FAKE_CLINICIAN_ID));
      act(() => {
        result.current.enter();
        result.current.setContent("   ");
      });

      await act(async () => {
        await result.current.submit();
      });

      expect(mockCorrect).not.toHaveBeenCalled();
    });
  });
});
