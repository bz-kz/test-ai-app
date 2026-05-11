import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import DraftPage from "../page";

// useGenerateDraft フックをモック — 実際のサービス/fetch は使わない
vi.mock("@/hooks/useGenerateDraft", () => ({
  useGenerateDraft: vi.fn(),
}));

import { useGenerateDraft } from "@/hooks/useGenerateDraft";

const mockUseGenerateDraft = vi.mocked(useGenerateDraft);

const FAKE_ENCOUNTER_ID = "00000000-0000-0000-0000-000000000010";

const FAKE_DRAFT = {
  id: "00000000-0000-0000-0000-000000000020",
  encounter_id: FAKE_ENCOUNTER_ID,
  content: "S: 頭痛。\nO: 正常。\nA: 緊張性頭痛。\nP: 経過観察。",
  confidence: 0.85,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

/** テスト用のデフォルトフック戻り値 */
function makeHookReturn(overrides: Partial<ReturnType<typeof useGenerateDraft>>) {
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

/** Next.js 15 の async params を模倣する */
function makeParams(encounterId: string): Promise<{ encounterId: string }> {
  return Promise.resolve({ encounterId });
}

/**
 * React.use(params) は Promise を Suspense で処理するため、
 * render の解決まで act でラップして Promise を flush する必要がある。
 */
async function renderPage(overrides: Partial<ReturnType<typeof useGenerateDraft>> = {}) {
  mockUseGenerateDraft.mockReturnValue(makeHookReturn(overrides));
  await act(async () => {
    render(<DraftPage params={makeParams(FAKE_ENCOUNTER_ID)} />);
  });
}

describe("DraftPage", () => {
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
    // 200ms は spinner tier 未満なので aria-busy は設定されない
    expect(button).not.toHaveAttribute("aria-busy", "true");
    // スケルトンはまだ表示されない
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
    // hint はまだ表示されない
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
    // キャンセルボタンはまだ表示されない
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
