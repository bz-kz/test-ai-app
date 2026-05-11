import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import PatientsPage from "../page";

// useMrnSearch フックをモック — 実際のデバウンス/fetch は使わない
vi.mock("@/hooks/useMrnSearch", () => ({
  useMrnSearch: vi.fn(),
}));

import { useMrnSearch } from "@/hooks/useMrnSearch";

const mockUseMrnSearch = vi.mocked(useMrnSearch);

const FAKE_PATIENT = {
  id: "00000000-0000-0000-0000-000000000001",
  mrn: "MRN-TEST-001",
  family_name: "山田",
  given_name: "太郎",
  date_of_birth: "1990-01-01",
  created_at: "2024-01-01T00:00:00Z",
};

describe("PatientsPage", () => {
  it("idle 状態: プレースホルダテキストが表示される", () => {
    mockUseMrnSearch.mockReturnValue({
      query: "",
      setQuery: vi.fn(),
      status: "idle",
      result: null,
    });

    render(<PatientsPage />);
    expect(screen.getByText("MRN を入力すると患者カードが表示されます")).toBeInTheDocument();
  });

  it("searching 状態: 検索ボタンがローディング状態になる", () => {
    mockUseMrnSearch.mockReturnValue({
      query: "MRN-TEST-001",
      setQuery: vi.fn(),
      status: "searching",
      result: null,
    });

    render(<PatientsPage />);
    // ローディング中のボタンは aria-busy=true
    expect(screen.getByRole("button", { name: "検索中" })).toHaveAttribute("aria-busy", "true");
  });

  it("found 状態: 患者情報カードが表示される", () => {
    mockUseMrnSearch.mockReturnValue({
      query: "MRN-TEST-001",
      setQuery: vi.fn(),
      status: "found",
      result: FAKE_PATIENT,
    });

    render(<PatientsPage />);
    expect(screen.getByText("山田 太郎")).toBeInTheDocument();
    expect(screen.getByText("MRN-TEST-001")).toBeInTheDocument();
    expect(screen.getByText("1990-01-01")).toBeInTheDocument();
  });

  it("not_found 状態: 該当患者なしメッセージが表示される", () => {
    mockUseMrnSearch.mockReturnValue({
      query: "MRN-UNKNOWN",
      setQuery: vi.fn(),
      status: "not_found",
      result: null,
    });

    render(<PatientsPage />);
    expect(screen.getByText("該当患者なし")).toBeInTheDocument();
  });

  it("error 状態: エラーメッセージが表示される", () => {
    mockUseMrnSearch.mockReturnValue({
      query: "MRN-ERR",
      setQuery: vi.fn(),
      status: "error",
      result: null,
    });

    render(<PatientsPage />);
    // role=alert の要素にエラーメッセージが表示される
    expect(screen.getByRole("alert")).toHaveTextContent(
      "検索に失敗しました。時間をおいて再試行してください。"
    );
  });
});
