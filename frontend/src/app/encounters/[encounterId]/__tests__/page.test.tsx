import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// useEncounterDetail フックをモック — 実際のフェッチは呼び出さない
vi.mock("@/hooks/useEncounterDetail", () => ({
  useEncounterDetail: vi.fn(),
}));

import { useEncounterDetail } from "@/hooks/useEncounterDetail";
import EncounterDetailPage from "../page";

const mockUseEncounterDetail = vi.mocked(useEncounterDetail);

const ENCOUNTER_ID = "00000000-0000-0000-0000-000000000010";
const PATIENT_ID = "00000000-0000-0000-0000-000000000001";
const CLINICIAN_ID = "00000000-0000-0000-0000-0000000a11ce";

const FAKE_ENCOUNTER = {
  id: ENCOUNTER_ID,
  patient_id: PATIENT_ID,
  encountered_at: "2024-06-15T00:00:00Z",
  clinician_id: CLINICIAN_ID,
  created_at: "2024-06-15T09:00:00Z",
};

const FAKE_DRAFT_1 = {
  id: "00000000-0000-0000-0000-000000000021",
  encounter_id: ENCOUNTER_ID,
  content: "S: 頭痛。O: 正常。A: 緊張性頭痛。P: 経過観察。",
  confidence: 0.85,
  created_at: "2024-06-15T10:00:00Z",
  updated_at: "2024-06-15T10:00:00Z",
};

const FAKE_DRAFT_2 = {
  id: "00000000-0000-0000-0000-000000000022",
  encounter_id: ENCOUNTER_ID,
  content: "S: 古い下書き内容。",
  confidence: 0.7,
  created_at: "2024-06-15T09:30:00Z",
  updated_at: "2024-06-15T09:30:00Z",
};

const FAKE_FINAL_1 = {
  id: "00000000-0000-0000-0000-000000000031",
  encounter_id: ENCOUNTER_ID,
  content: "S: 確定カルテ内容。O: 正常。A: 診断。P: 処方。",
  confidence: 0.9,
  clinician_id: CLINICIAN_ID,
  predecessor_id: null,
  created_at: "2024-06-15T11:00:00Z",
};

/** Next.js 15 の async params を模倣する */
function makeParams(): Promise<{ encounterId: string }> {
  return Promise.resolve({ encounterId: ENCOUNTER_ID });
}

/** await act でラップして Promise を flush する */
async function renderPage() {
  await act(async () => {
    render(<EncounterDetailPage params={makeParams()} />);
  });
}

describe("EncounterDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loading 状態: 読み込み中テキストが表示される", async () => {
    mockUseEncounterDetail.mockReturnValue({
      status: "loading",
      encounter: null,
      drafts: [],
      finals: [],
      error: null,
      load: vi.fn(),
    });

    await renderPage();
    expect(screen.getByText("読み込み中…")).toBeInTheDocument();
  });

  it("idle 状態: 読み込み中テキストが表示される", async () => {
    mockUseEncounterDetail.mockReturnValue({
      status: "idle",
      encounter: null,
      drafts: [],
      finals: [],
      error: null,
      load: vi.fn(),
    });

    await renderPage();
    expect(screen.getByText("読み込み中…")).toBeInTheDocument();
  });

  it("not_found 状態: 受診が見つかりませんメッセージが表示される", async () => {
    mockUseEncounterDetail.mockReturnValue({
      status: "not_found",
      encounter: null,
      drafts: [],
      finals: [],
      error: null,
      load: vi.fn(),
    });

    await renderPage();
    expect(screen.getByText("受診が見つかりません")).toBeInTheDocument();
  });

  it("error 状態: エラーメッセージが role=alert で表示される", async () => {
    mockUseEncounterDetail.mockReturnValue({
      status: "error",
      encounter: null,
      drafts: [],
      finals: [],
      error: "受診情報の取得に失敗しました。",
      load: vi.fn(),
    });

    await renderPage();
    expect(screen.getByRole("alert")).toHaveTextContent("受診情報の取得に失敗しました");
  });

  it("loaded 状態: clinician_id が最初の 8 hex 文字 + … で表示される", async () => {
    mockUseEncounterDetail.mockReturnValue({
      status: "loaded",
      encounter: FAKE_ENCOUNTER,
      drafts: [],
      finals: [],
      error: null,
      load: vi.fn(),
    });

    await renderPage();
    // CLINICIAN_ID = "00000000-0000-0000-0000-0000000a11ce"
    // ハイフン除去 → "000000000000000000000000000a11ce"
    // 最初の 8 文字 → "00000000"
    expect(screen.getByText("00000000…")).toBeInTheDocument();
  });

  it("loaded 状態: 下書きを作成/編集 リンクの href が正しい", async () => {
    mockUseEncounterDetail.mockReturnValue({
      status: "loaded",
      encounter: FAKE_ENCOUNTER,
      drafts: [],
      finals: [],
      error: null,
      load: vi.fn(),
    });

    await renderPage();
    const draftLink = screen.getByRole("link", { name: "下書きを作成 / 編集" });
    expect(draftLink).toHaveAttribute("href", `/encounters/${ENCOUNTER_ID}/draft`);
  });

  it("下書き一覧: 内容の最初の 80 文字が表示され長いコンテンツは省略される", async () => {
    // 80 文字を超える長いコンテンツ (日本語)
    const longContent = "A".repeat(90);
    const draftWithLongContent = {
      ...FAKE_DRAFT_1,
      content: longContent,
    };

    mockUseEncounterDetail.mockReturnValue({
      status: "loaded",
      encounter: FAKE_ENCOUNTER,
      drafts: [draftWithLongContent, FAKE_DRAFT_2],
      finals: [],
      error: null,
      load: vi.fn(),
    });

    await renderPage();

    // 80 文字以上のコンテンツは省略される
    const expectedExcerpt = `${"A".repeat(80)}…`;
    expect(screen.getByText(expectedExcerpt)).toBeInTheDocument();
    // 2 番目の下書きは 80 文字未満なのでそのまま表示される
    expect(screen.getByText(FAKE_DRAFT_2.content)).toBeInTheDocument();
  });

  it("確定カルテ一覧: コンテンツが表示される", async () => {
    mockUseEncounterDetail.mockReturnValue({
      status: "loaded",
      encounter: FAKE_ENCOUNTER,
      drafts: [],
      finals: [FAKE_FINAL_1],
      error: null,
      load: vi.fn(),
    });

    await renderPage();
    // FAKE_FINAL_1.content は 80 文字未満なのでそのまま表示される
    expect(screen.getByText(FAKE_FINAL_1.content)).toBeInTheDocument();
  });

  it("下書きと確定カルテが空の場合: それぞれの空状態メッセージが表示される", async () => {
    mockUseEncounterDetail.mockReturnValue({
      status: "loaded",
      encounter: FAKE_ENCOUNTER,
      drafts: [],
      finals: [],
      error: null,
      load: vi.fn(),
    });

    await renderPage();
    expect(screen.getByText("下書きがありません")).toBeInTheDocument();
    expect(screen.getByText("確定カルテがありません")).toBeInTheDocument();
  });
});
