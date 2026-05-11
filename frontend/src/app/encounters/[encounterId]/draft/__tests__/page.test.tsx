import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import DraftPage from "../page";

// useGenerateDraft フックをモック — 実際のサービス/fetch は使わない
vi.mock("@/hooks/useGenerateDraft", () => ({
  useGenerateDraft: vi.fn(),
}));

// useDraftLifecycle フックをモック
vi.mock("@/hooks/useDraftLifecycle", () => ({
  useDraftLifecycle: vi.fn(),
}));

import { useGenerateDraft } from "@/hooks/useGenerateDraft";
import { useDraftLifecycle } from "@/hooks/useDraftLifecycle";

const mockUseGenerateDraft = vi.mocked(useGenerateDraft);
const mockUseDraftLifecycle = vi.mocked(useDraftLifecycle);

const FAKE_ENCOUNTER_ID = "00000000-0000-0000-0000-000000000010";
const FAKE_DRAFT_ID = "00000000-0000-0000-0000-000000000020";
const FAKE_FINAL_ID = "00000000-0000-0000-0000-000000000030";
const FAKE_CLINICIAN_ID = "00000000-0000-0000-0000-000000000001";

const FAKE_DRAFT = {
  id: FAKE_DRAFT_ID,
  encounter_id: FAKE_ENCOUNTER_ID,
  content: "S: 頭痛。\nO: 正常。\nA: 緊張性頭痛。\nP: 経過観察。",
  confidence: 0.85,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

const FAKE_DRAFT_LOW_CONFIDENCE = {
  ...FAKE_DRAFT,
  confidence: 0.3,
};

const FAKE_FINAL = {
  id: FAKE_FINAL_ID,
  encounter_id: FAKE_ENCOUNTER_ID,
  content: "S: 頭痛。\nO: 正常。\nA: 確定診断。",
  confidence: 0.85,
  clinician_id: FAKE_CLINICIAN_ID,
  predecessor_id: null,
  created_at: "2024-01-01T00:00:00Z",
};

/** テスト用のデフォルト useGenerateDraft 戻り値 */
function makeGenerateReturn(overrides: Partial<ReturnType<typeof useGenerateDraft>>) {
  return {
    clinicalInput: "",
    setClinicalInput: vi.fn(),
    status: "idle" as const,
    draft: null,
    error: null,
    generate: vi.fn(),
    cancel: vi.fn(),
    elapsedMs: 0,
    ...overrides,
  };
}

/** テスト用のデフォルト useDraftLifecycle 戻り値 */
function makeLifecycleReturn(overrides: Partial<ReturnType<typeof useDraftLifecycle>>) {
  return {
    mode: "view" as const,
    editContent: "",
    setEditContent: vi.fn(),
    enterEditMode: vi.fn(),
    cancelEdit: vi.fn(),
    saveEdit: vi.fn().mockResolvedValue(undefined),
    approve: vi.fn().mockResolvedValue(undefined),
    final: null,
    status: "idle" as const,
    error: null,
    ...overrides,
  };
}

/** Next.js 15 の async params を模倣する */
function makeParams(encounterId: string): Promise<{ encounterId: string }> {
  return Promise.resolve({ encounterId });
}

/**
 * React.use(params) は Promise を Suspense で処理するため、
 * render の解決まで act でラップして Promise を flush する必要がある。
 */
async function renderPage(
  generateOverrides: Partial<ReturnType<typeof useGenerateDraft>> = {},
  lifecycleOverrides: Partial<ReturnType<typeof useDraftLifecycle>> = {}
) {
  mockUseGenerateDraft.mockReturnValue(makeGenerateReturn(generateOverrides));
  mockUseDraftLifecycle.mockReturnValue(makeLifecycleReturn(lifecycleOverrides));
  await act(async () => {
    render(<DraftPage params={makeParams(FAKE_ENCOUNTER_ID)} />);
  });
}

// ============================================================
// FE-003 の既存テスト (latency UX tiers)
// ============================================================

describe("DraftPage (FE-003: latency UX tiers)", () => {
  it("idle 状態: 案内テキストが表示される", async () => {
    await renderPage({ status: "idle", draft: null });
    expect(
      screen.getByText("臨床入力を記入して『下書きを生成』を押してください")
    ).toBeInTheDocument();
  });

  it("idle 状態: 生成ボタンが表示される", async () => {
    await renderPage({ status: "idle" });
    expect(screen.getByRole("button", { name: "下書きを生成" })).toBeInTheDocument();
  });

  it("generating かつ elapsedMs < 1000: ボタンはスピナーなし (invisible tier)", async () => {
    await renderPage({
      status: "generating",
      clinicalInput: "入力済み",
      elapsedMs: 200,
    });
    const button = screen.getByRole("button", { name: "下書きを生成" });
    expect(button).not.toHaveAttribute("aria-busy", "true");
    expect(screen.queryByLabelText("生成中")).toBeNull();
  });

  it("generating かつ elapsedMs >= 300: ボタンがスピナー状態になる (spinner tier)", async () => {
    await renderPage({
      status: "generating",
      clinicalInput: "入力済み",
      elapsedMs: 500,
    });
    const button = screen.getByRole("button", { name: "下書きを生成" });
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("generating かつ elapsedMs >= 1000: スケルトンが表示される (skeleton tier)", async () => {
    await renderPage({
      status: "generating",
      clinicalInput: "入力済み",
      elapsedMs: 1500,
    });
    expect(screen.getByLabelText("生成中")).toBeInTheDocument();
    expect(screen.queryByText("ローカルモデル応答待ち…")).toBeNull();
  });

  it("generating かつ elapsedMs >= 3000: スケルトン + ヒントが表示される (hint tier)", async () => {
    await renderPage({
      status: "generating",
      clinicalInput: "入力済み",
      elapsedMs: 5000,
    });
    expect(screen.getByLabelText("生成中")).toBeInTheDocument();
    expect(screen.getByText("ローカルモデル応答待ち…")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "キャンセル" })).toBeNull();
  });

  it("generating かつ elapsedMs >= 10000: スケルトン + ヒント + キャンセルボタンが表示される (cancel tier)", async () => {
    await renderPage({
      status: "generating",
      clinicalInput: "入力済み",
      elapsedMs: 12000,
    });
    expect(screen.getByLabelText("生成中")).toBeInTheDocument();
    expect(screen.getByText("ローカルモデル応答待ち…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "キャンセル" })).toBeInTheDocument();
  });

  it("success 状態: AIIndicatedText で下書き内容が表示される", async () => {
    await renderPage({
      status: "success",
      draft: FAKE_DRAFT,
    });
    expect(screen.getByRole("article", { name: "AI 生成テキスト" })).toBeInTheDocument();
    expect(screen.getByText(/S: 頭痛/)).toBeInTheDocument();
  });

  it("encounter_not_found 状態: エラーメッセージが表示される", async () => {
    await renderPage({
      status: "encounter_not_found",
      error: "Encounter が見つかりません。",
    });
    expect(screen.getByRole("alert")).toHaveTextContent("Encounter が見つかりません。");
  });

  it("inference_unavailable 状態: エラーメッセージが表示される", async () => {
    await renderPage({
      status: "inference_unavailable",
      error: "推論サービスが一時的に利用できません。しばらく待って再試行してください。",
    });
    expect(screen.getByRole("alert")).toHaveTextContent("推論サービスが一時的に利用できません");
  });

  it("error 状態: 汎用エラーメッセージが表示される", async () => {
    await renderPage({
      status: "error",
      error: "下書きの生成に失敗しました。",
    });
    expect(screen.getByRole("alert")).toHaveTextContent("下書きの生成に失敗しました。");
  });

  it("clinicalInput が空の場合は生成ボタンが disabled になる", async () => {
    await renderPage({ clinicalInput: "" });
    expect(screen.getByRole("button", { name: "下書きを生成" })).toBeDisabled();
  });

  it("clinicalInput が空白のみの場合も生成ボタンが disabled になる", async () => {
    await renderPage({ clinicalInput: "   " });
    expect(screen.getByRole("button", { name: "下書きを生成" })).toBeDisabled();
  });
});

// ============================================================
// FE-004 の追加テスト
// ============================================================

describe("DraftPage (FE-004: view mode action buttons)", () => {
  it("success+view モードで 3 つのアクションボタンが正しい順序で表示される", async () => {
    await renderPage({ status: "success", draft: FAKE_DRAFT }, { mode: "view" });
    const buttons = screen.getAllByRole("button");
    // 生成ボタンは非表示 (view モード)
    const actionButtons = buttons.filter((b) =>
      ["再生成", "編集", "承認"].includes(b.textContent?.trim() ?? "")
    );
    expect(actionButtons[0]).toHaveTextContent("再生成");
    expect(actionButtons[1]).toHaveTextContent("編集");
    expect(actionButtons[2]).toHaveTextContent("承認");
  });

  it("success+view モードで ConfidencePill が表示される (confidence != null)", async () => {
    await renderPage({ status: "success", draft: FAKE_DRAFT }, { mode: "view" });
    // confidence 0.85 は neutral バリアント
    expect(screen.getByText("信頼度 0.85")).toBeInTheDocument();
  });

  it("confidence ≤ 0.5 のとき ConfidencePill は warning バリアントになる", async () => {
    await renderPage({ status: "success", draft: FAKE_DRAFT_LOW_CONFIDENCE }, { mode: "view" });
    const pill = screen.getByRole("status", { name: "AI 信頼度 0.30" });
    expect(pill).toBeInTheDocument();
    expect(pill.className).toMatch(/bg-warning\/10/);
  });

  it("confidence が null のとき ConfidencePill は表示されない", async () => {
    await renderPage(
      { status: "success", draft: { ...FAKE_DRAFT, confidence: null } },
      { mode: "view" }
    );
    expect(screen.queryByRole("status", { name: /AI 信頼度/ })).toBeNull();
  });
});

describe("DraftPage (FE-004: editing mode)", () => {
  it("editing モードでは TextArea が表示される", async () => {
    await renderPage(
      { status: "success", draft: FAKE_DRAFT },
      { mode: "editing", editContent: "編集中のテキスト" }
    );
    const textarea = screen.getByRole("textbox", { name: "下書き編集" });
    expect(textarea).toBeInTheDocument();
  });

  it("editing モードでは キャンセル と 更新 ボタンが表示される", async () => {
    await renderPage(
      { status: "success", draft: FAKE_DRAFT },
      { mode: "editing", editContent: "内容" }
    );
    expect(screen.getByRole("button", { name: "キャンセル" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "更新" })).toBeInTheDocument();
  });

  it("editing モードでは 再生成/編集/承認 ボタンは非表示になる", async () => {
    await renderPage(
      { status: "success", draft: FAKE_DRAFT },
      { mode: "editing", editContent: "内容" }
    );
    expect(screen.queryByRole("button", { name: "再生成" })).toBeNull();
    expect(screen.queryByRole("button", { name: "編集" })).toBeNull();
    expect(screen.queryByRole("button", { name: "承認" })).toBeNull();
  });

  it("editContent が空白のみの場合は 更新 ボタンが disabled になる", async () => {
    await renderPage(
      { status: "success", draft: FAKE_DRAFT },
      { mode: "editing", editContent: "   " }
    );
    expect(screen.getByRole("button", { name: "更新" })).toBeDisabled();
  });

  it("saving 中は 更新 ボタンが loading 状態になる", async () => {
    await renderPage(
      { status: "success", draft: FAKE_DRAFT },
      { mode: "editing", editContent: "内容", status: "saving" }
    );
    const saveButton = screen.getByRole("button", { name: "更新" });
    expect(saveButton).toHaveAttribute("aria-busy", "true");
  });
});

describe("DraftPage (FE-004: finalized mode)", () => {
  it("finalized モードでは 確定済み バッジが表示される", async () => {
    await renderPage(
      { status: "success", draft: FAKE_DRAFT },
      { mode: "finalized", final: FAKE_FINAL }
    );
    expect(screen.getByRole("status", { name: "確定済みカルテ" })).toBeInTheDocument();
  });

  it("finalized モードではアクションボタン (再生成/編集/承認) が表示されない", async () => {
    await renderPage(
      { status: "success", draft: FAKE_DRAFT },
      { mode: "finalized", final: FAKE_FINAL }
    );
    expect(screen.queryByRole("button", { name: "再生成" })).toBeNull();
    expect(screen.queryByRole("button", { name: "編集" })).toBeNull();
    expect(screen.queryByRole("button", { name: "承認" })).toBeNull();
  });

  it("finalized モードでは確定カルテの内容が表示される", async () => {
    await renderPage(
      { status: "success", draft: FAKE_DRAFT },
      { mode: "finalized", final: FAKE_FINAL }
    );
    expect(screen.getByText(/S: 頭痛。/)).toBeInTheDocument();
  });

  it("finalized モードでは '確定カルテ' ラベルの AIIndicatedText が使われる", async () => {
    await renderPage(
      { status: "success", draft: FAKE_DRAFT },
      { mode: "finalized", final: FAKE_FINAL }
    );
    // AIIndicatedText の label="確定カルテ"
    expect(screen.getByText("確定カルテ")).toBeInTheDocument();
  });
});

describe("DraftPage (FE-004: error states from lifecycle)", () => {
  it("view モードで承認エラー時に alert が表示される", async () => {
    await renderPage(
      { status: "success", draft: FAKE_DRAFT },
      {
        mode: "view",
        status: "error",
        error: "下書きが見つかりません。ページを再読み込みしてください。",
      }
    );
    expect(screen.getByRole("alert")).toHaveTextContent("下書きが見つかりません");
  });

  it("view モードで encounter_already_finalized エラー時に適切なメッセージが表示される", async () => {
    await renderPage(
      { status: "success", draft: FAKE_DRAFT },
      { mode: "view", status: "error", error: "この受診には既に確定カルテが存在します。" }
    );
    expect(screen.getByRole("alert")).toHaveTextContent("既に確定カルテが存在します");
  });

  it("editing モードでエラー時に alert が表示される", async () => {
    await renderPage(
      { status: "success", draft: FAKE_DRAFT },
      {
        mode: "editing",
        editContent: "内容",
        status: "error",
        error: "エラーが発生しました。もう一度お試しください。",
      }
    );
    expect(screen.getByRole("alert")).toHaveTextContent("エラーが発生しました");
  });
});
