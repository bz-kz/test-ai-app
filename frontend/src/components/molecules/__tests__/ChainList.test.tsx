import { render, screen, within } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import ChainList from "../ChainList";
import type { RecordFinal } from "@/types/recordFinal";

const FAKE_ENCOUNTER_ID = "00000000-0000-0000-0000-000000000010";
const FAKE_CLINICIAN_ID = "00000000-0000-0000-0000-000000000001";

const FAKE_FINAL_V1: RecordFinal = {
  id: "00000000-0000-0000-0000-000000000031",
  encounter_id: FAKE_ENCOUNTER_ID,
  content: "S: 最初の確定カルテ。O: バイタル正常。A: 緊張性頭痛。P: 経過観察。",
  confidence: 0.85,
  clinician_id: FAKE_CLINICIAN_ID,
  predecessor_id: null,
  created_at: "2024-01-01T00:00:00Z",
};

const FAKE_FINAL_V2: RecordFinal = {
  id: "00000000-0000-0000-0000-000000000032",
  encounter_id: FAKE_ENCOUNTER_ID,
  content: "S: 訂正後の確定カルテ。O: バイタル正常。A: 緊張性頭痛 (訂正)。P: 経過観察。",
  confidence: null,
  clinician_id: FAKE_CLINICIAN_ID,
  predecessor_id: FAKE_FINAL_V1.id,
  created_at: "2024-01-02T00:00:00Z",
};

// 80 文字を超えるコンテンツ
const LONG_CONTENT = "A".repeat(90);
const FAKE_FINAL_LONG: RecordFinal = {
  id: "00000000-0000-0000-0000-000000000033",
  encounter_id: FAKE_ENCOUNTER_ID,
  content: LONG_CONTENT,
  confidence: null,
  clinician_id: FAKE_CLINICIAN_ID,
  predecessor_id: null,
  created_at: "2024-01-03T00:00:00Z",
};

describe("ChainList", () => {
  it("chain が空のとき何も描画しない", () => {
    const { container } = render(<ChainList chain={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("chain のエントリ数だけ <li> が描画される", () => {
    render(<ChainList chain={[FAKE_FINAL_V1, FAKE_FINAL_V2]} />);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
  });

  it("oldest → newest 順 (先頭が第1版、末尾が最新版) で描画される", () => {
    render(<ChainList chain={[FAKE_FINAL_V1, FAKE_FINAL_V2]} />);
    const items = screen.getAllByRole("listitem");
    // 第1版は先頭エントリに "第1版" テキストを含む
    expect(within(items[0]).getByText(/第1版/)).toBeInTheDocument();
    // 第2版は末尾エントリに "第2版" テキストを含む
    expect(within(items[1]).getByText(/第2版/)).toBeInTheDocument();
  });

  it("最終エントリ (chain head) は font-bold クラスを持ち、それ以外は font-normal", () => {
    render(<ChainList chain={[FAKE_FINAL_V1, FAKE_FINAL_V2]} />);
    const items = screen.getAllByRole("listitem");
    expect(items[0]).not.toHaveClass("font-bold");
    expect(items[1]).toHaveClass("font-bold");
  });

  it("content が 80 文字を超えるとき省略記号 (…) が付与される", () => {
    render(<ChainList chain={[FAKE_FINAL_LONG]} />);
    const item = screen.getByRole("listitem");
    // 省略記号を含む
    expect(item.textContent).toContain("…");
    // 元のコンテンツ全体は表示されない (81 文字目以降は切り捨て)
    expect(item.textContent).not.toContain("A".repeat(90));
  });

  it("content が 80 文字以下のとき省略記号は付与されない", () => {
    render(<ChainList chain={[FAKE_FINAL_V1]} />);
    const item = screen.getByRole("listitem");
    expect(item.textContent).not.toContain("…");
  });

  it("各 <li> の aria-label が '第N版' と確定日時を含む", () => {
    render(<ChainList chain={[FAKE_FINAL_V1, FAKE_FINAL_V2]} />);
    const items = screen.getAllByRole("listitem");
    // 第1版
    expect(items[0]).toHaveAttribute("aria-label", expect.stringContaining("第1版"));
    expect(items[0]).toHaveAttribute("aria-label", expect.stringContaining("確定:"));
    // 第2版
    expect(items[1]).toHaveAttribute("aria-label", expect.stringContaining("第2版"));
    expect(items[1]).toHaveAttribute("aria-label", expect.stringContaining("確定:"));
  });

  it("デフォルトラベル '訂正履歴' が section の aria-label として使われる", () => {
    render(<ChainList chain={[FAKE_FINAL_V1]} />);
    expect(screen.getByRole("region", { name: "訂正履歴" })).toBeInTheDocument();
  });

  it("label prop を渡すとその値が section の aria-label になる", () => {
    render(<ChainList chain={[FAKE_FINAL_V1]} label="カスタムラベル" />);
    expect(screen.getByRole("region", { name: "カスタムラベル" })).toBeInTheDocument();
  });
});
