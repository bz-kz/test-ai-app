import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useDraftLifecycle } from "../useDraftLifecycle";
import type { RecordFinal } from "@/types/recordFinal";

// サービス層をモック — 実際の fetch は呼び出さない
vi.mock("@/services/drafts", () => ({
  editRecordDraft: vi.fn(),
  finalizeRecordDraft: vi.fn(),
}));

import { editRecordDraft, finalizeRecordDraft } from "@/services/drafts";

const mockEdit = vi.mocked(editRecordDraft);
const mockFinalize = vi.mocked(finalizeRecordDraft);

const FAKE_ENCOUNTER_ID = "00000000-0000-0000-0000-000000000010";
const FAKE_DRAFT_ID = "00000000-0000-0000-0000-000000000020";
const FAKE_FINAL_ID = "00000000-0000-0000-0000-000000000030";
const FAKE_CLINICIAN_ID = "00000000-0000-0000-0000-000000000001";

const FAKE_DRAFT = {
  id: FAKE_DRAFT_ID,
  encounter_id: FAKE_ENCOUNTER_ID,
  content: "S: 頭痛。\nO: 正常。",
  confidence: 0.85,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

const FAKE_FINAL: RecordFinal = {
  id: FAKE_FINAL_ID,
  encounter_id: FAKE_ENCOUNTER_ID,
  content: "S: 頭痛。\nO: 正常。",
  confidence: 0.85,
  clinician_id: FAKE_CLINICIAN_ID,
  predecessor_id: null,
  created_at: "2024-01-01T00:00:00Z",
};

describe("useDraftLifecycle", () => {
  beforeEach(() => {
    mockEdit.mockReset();
    mockFinalize.mockReset();
  });

  it("初期状態は mode=view, status=idle, error=null, final=null", () => {
    const { result } = renderHook(() => useDraftLifecycle(FAKE_DRAFT));
    expect(result.current.mode).toBe("view");
    expect(result.current.status).toBe("idle");
    expect(result.current.error).toBeNull();
    expect(result.current.final).toBeNull();
  });

  describe("enterEditMode", () => {
    it("view → editing に遷移し、editContent が draft.content で初期化される", () => {
      const { result } = renderHook(() => useDraftLifecycle(FAKE_DRAFT));
      act(() => {
        result.current.enterEditMode();
      });
      expect(result.current.mode).toBe("editing");
      expect(result.current.editContent).toBe(FAKE_DRAFT.content);
    });

    it("draft が null のとき enterEditMode は何もしない", () => {
      const { result } = renderHook(() => useDraftLifecycle(null));
      act(() => {
        result.current.enterEditMode();
      });
      expect(result.current.mode).toBe("view");
    });
  });

  describe("cancelEdit", () => {
    it("editing → view に戻り、editContent が空になる", () => {
      const { result } = renderHook(() => useDraftLifecycle(FAKE_DRAFT));
      act(() => {
        result.current.enterEditMode();
      });
      expect(result.current.mode).toBe("editing");

      act(() => {
        result.current.cancelEdit();
      });
      expect(result.current.mode).toBe("view");
      expect(result.current.editContent).toBe("");
    });

    it("status が error のときに cancelEdit を呼ぶと idle に戻る", () => {
      const { result } = renderHook(() => useDraftLifecycle(FAKE_DRAFT));
      act(() => {
        result.current.enterEditMode();
      });
      act(() => {
        result.current.cancelEdit();
      });
      expect(result.current.status).toBe("idle");
      expect(result.current.error).toBeNull();
    });
  });

  describe("saveEdit", () => {
    it("成功時: view に戻り editContent が空になる", async () => {
      const updatedDraft = { ...FAKE_DRAFT, content: "更新後の内容" };
      mockEdit.mockResolvedValueOnce({ kind: "updated", draft: updatedDraft });

      const { result } = renderHook(() => useDraftLifecycle(FAKE_DRAFT));

      act(() => {
        result.current.enterEditMode();
        result.current.setEditContent("更新後の内容");
      });

      await act(async () => {
        await result.current.saveEdit();
      });

      expect(result.current.mode).toBe("view");
      expect(result.current.editContent).toBe("");
      expect(result.current.status).toBe("idle");
      expect(result.current.error).toBeNull();
    });

    it("saveEdit 中は status が saving になる", async () => {
      // 永遠に pending (解決されない)
      mockEdit.mockImplementation(() => new Promise<never>(() => undefined));

      const { result } = renderHook(() => useDraftLifecycle(FAKE_DRAFT));

      act(() => {
        result.current.enterEditMode();
        result.current.setEditContent("新しい内容");
      });

      // saveEdit は非同期 — status が saving になることを確認
      act(() => {
        void result.current.saveEdit();
      });

      expect(result.current.status).toBe("saving");
    });

    it("draft_not_found: status=error と日本語エラーメッセージが設定される", async () => {
      mockEdit.mockResolvedValueOnce({ kind: "draft_not_found" });

      const { result } = renderHook(() => useDraftLifecycle(FAKE_DRAFT));

      act(() => {
        result.current.enterEditMode();
        result.current.setEditContent("内容");
      });

      await act(async () => {
        await result.current.saveEdit();
      });

      expect(result.current.status).toBe("error");
      expect(result.current.error).toMatch(/下書きが見つかりません/);
      // 編集モードは維持される
      expect(result.current.mode).toBe("editing");
    });

    it("validation_error: status=error と日本語エラーメッセージが設定される", async () => {
      mockEdit.mockResolvedValueOnce({ kind: "validation_error", fields: ["content"] });

      const { result } = renderHook(() => useDraftLifecycle(FAKE_DRAFT));

      act(() => {
        result.current.enterEditMode();
        result.current.setEditContent("内容");
      });

      await act(async () => {
        await result.current.saveEdit();
      });

      expect(result.current.status).toBe("error");
      expect(result.current.error).toMatch(/入力内容に問題があります/);
    });

    it("error: status=error と汎用エラーメッセージが設定される", async () => {
      mockEdit.mockResolvedValueOnce({ kind: "error" });

      const { result } = renderHook(() => useDraftLifecycle(FAKE_DRAFT));

      act(() => {
        result.current.enterEditMode();
        result.current.setEditContent("内容");
      });

      await act(async () => {
        await result.current.saveEdit();
      });

      expect(result.current.status).toBe("error");
      expect(result.current.error).toMatch(/エラーが発生しました/);
    });

    it("editContent が空白のみの場合は saveEdit が何もしない", async () => {
      const { result } = renderHook(() => useDraftLifecycle(FAKE_DRAFT));

      act(() => {
        result.current.enterEditMode();
        result.current.setEditContent("   ");
      });

      await act(async () => {
        await result.current.saveEdit();
      });

      // apiFetch は呼ばれない
      expect(mockEdit).not.toHaveBeenCalled();
    });

    it("成功時: onDraftUpdated コールバックが更新後の RecordDraft で呼ばれる", async () => {
      const updatedDraft = { ...FAKE_DRAFT, content: "更新後の内容" };
      mockEdit.mockResolvedValueOnce({ kind: "updated", draft: updatedDraft });

      const onDraftUpdated = vi.fn();
      const { result } = renderHook(() => useDraftLifecycle(FAKE_DRAFT, { onDraftUpdated }));

      act(() => {
        result.current.enterEditMode();
        result.current.setEditContent("更新後の内容");
      });

      await act(async () => {
        await result.current.saveEdit();
      });

      expect(onDraftUpdated).toHaveBeenCalledOnce();
      expect(onDraftUpdated).toHaveBeenCalledWith(updatedDraft);
    });
  });

  describe("approve", () => {
    it("成功時: mode=finalized になり final が設定される", async () => {
      mockFinalize.mockResolvedValueOnce({ kind: "finalized", final: FAKE_FINAL });

      const { result } = renderHook(() => useDraftLifecycle(FAKE_DRAFT));

      await act(async () => {
        await result.current.approve();
      });

      expect(result.current.mode).toBe("finalized");
      expect(result.current.final).toEqual(FAKE_FINAL);
      expect(result.current.status).toBe("idle");
      expect(result.current.error).toBeNull();
    });

    it("approve 中は status が finalizing になる", async () => {
      mockFinalize.mockImplementation(() => new Promise<never>(() => undefined));

      const { result } = renderHook(() => useDraftLifecycle(FAKE_DRAFT));

      act(() => {
        void result.current.approve();
      });

      expect(result.current.status).toBe("finalizing");
    });

    it("draft_not_found: status=error と日本語エラーメッセージが設定される", async () => {
      mockFinalize.mockResolvedValueOnce({ kind: "draft_not_found" });

      const { result } = renderHook(() => useDraftLifecycle(FAKE_DRAFT));

      await act(async () => {
        await result.current.approve();
      });

      expect(result.current.status).toBe("error");
      expect(result.current.error).toMatch(/下書きが見つかりません/);
    });

    it("encounter_already_finalized: status=error と適切なメッセージが設定される", async () => {
      mockFinalize.mockResolvedValueOnce({ kind: "encounter_already_finalized" });

      const { result } = renderHook(() => useDraftLifecycle(FAKE_DRAFT));

      await act(async () => {
        await result.current.approve();
      });

      expect(result.current.status).toBe("error");
      expect(result.current.error).toMatch(/既に確定カルテが存在します/);
    });

    it("error: status=error と汎用エラーメッセージが設定される", async () => {
      mockFinalize.mockResolvedValueOnce({ kind: "error" });

      const { result } = renderHook(() => useDraftLifecycle(FAKE_DRAFT));

      await act(async () => {
        await result.current.approve();
      });

      expect(result.current.status).toBe("error");
      expect(result.current.error).toMatch(/エラーが発生しました/);
    });

    it("draft が null のとき approve は何もしない", async () => {
      const { result } = renderHook(() => useDraftLifecycle(null));

      await act(async () => {
        await result.current.approve();
      });

      expect(mockFinalize).not.toHaveBeenCalled();
      expect(result.current.mode).toBe("view");
    });
  });

  describe("cancelEdit が進行中リクエストをリセットする", () => {
    it("saving 中に cancelEdit を呼ぶと mode=view に戻り status=idle になる", async () => {
      // 永遠に pending (解決されない)
      mockEdit.mockImplementation(() => new Promise<never>(() => undefined));

      const { result } = renderHook(() => useDraftLifecycle(FAKE_DRAFT));

      act(() => {
        result.current.enterEditMode();
        result.current.setEditContent("内容");
      });

      // saveEdit を開始するが await しない
      act(() => {
        void result.current.saveEdit();
      });

      expect(result.current.status).toBe("saving");

      // キャンセル
      act(() => {
        result.current.cancelEdit();
      });

      expect(result.current.mode).toBe("view");
      expect(result.current.status).toBe("idle");
    });
  });

  // ============================================================
  // FE-010: initialFinal オプションのテスト (ラッチ挙動)
  // ============================================================

  describe("initialFinal オプション (FE-010)", () => {
    it("(i) initialFinal が非 null のとき、useEffect 完了後に mode=finalized かつ final がその値になる", async () => {
      const { result } = renderHook(() =>
        useDraftLifecycle(FAKE_DRAFT, { initialFinal: FAKE_FINAL })
      );
      // useEffect が同期的に flush されるまで待つ
      await act(async () => {
        await Promise.resolve();
      });
      expect(result.current.mode).toBe("finalized");
      expect(result.current.final).toEqual(FAKE_FINAL);
    });

    it("(ii) initialFinal が null のとき、デフォルトの mode=view かつ final=null が保たれる", async () => {
      const { result } = renderHook(() => useDraftLifecycle(FAKE_DRAFT, { initialFinal: null }));
      await act(async () => {
        await Promise.resolve();
      });
      expect(result.current.mode).toBe("view");
      expect(result.current.final).toBeNull();
    });

    it("(iii) ラッチ: 一度シード済みの後 initialFinal が変化しても mode は再シードされない", async () => {
      // 初回レンダーは initialFinal=FAKE_FINAL でシード → mode=finalized
      const FAKE_FINAL_2 = {
        ...FAKE_FINAL,
        id: "00000000-0000-0000-0000-000000000099",
        predecessor_id: FAKE_FINAL_ID,
      };
      let initialFinal: typeof FAKE_FINAL | null = FAKE_FINAL;
      const { result, rerender } = renderHook(() =>
        useDraftLifecycle(FAKE_DRAFT, { initialFinal })
      );
      await act(async () => {
        await Promise.resolve();
      });
      expect(result.current.mode).toBe("finalized");
      expect(result.current.final).toEqual(FAKE_FINAL);

      // initialFinal を別の RecordFinal に変更して再レンダー — ラッチにより再シードしない
      initialFinal = FAKE_FINAL_2;
      rerender();
      await act(async () => {
        await Promise.resolve();
      });

      // seededRef が true のため final は上書きされない
      expect(result.current.mode).toBe("finalized");
      expect(result.current.final).toEqual(FAKE_FINAL);
    });
  });
});
