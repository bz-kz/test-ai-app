import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// フックをモック — 実際のフェッチは呼び出さない
vi.mock("@/hooks/usePatientDetail", () => ({
  usePatientDetail: vi.fn(),
}));

vi.mock("@/hooks/useCreateEncounter", () => ({
  useCreateEncounter: vi.fn(),
}));

import { usePatientDetail } from "@/hooks/usePatientDetail";
import { useCreateEncounter } from "@/hooks/useCreateEncounter";
import PatientDetailPage from "../page";

const mockUsePatientDetail = vi.mocked(usePatientDetail);
const mockUseCreateEncounter = vi.mocked(useCreateEncounter);

const PATIENT_ID = "00000000-0000-0000-0000-000000000001";
const ENCOUNTER_ID_1 = "00000000-0000-0000-0000-000000000010";
const ENCOUNTER_ID_2 = "00000000-0000-0000-0000-000000000011";

const FAKE_PATIENT = {
  id: PATIENT_ID,
  mrn: "MRN-TEST-001",
  family_name: "山田",
  given_name: "太郎",
  date_of_birth: "1990-01-01",
  created_at: "2024-01-01T00:00:00Z",
};

const FAKE_ENCOUNTERS = [
  {
    id: ENCOUNTER_ID_1,
    patient_id: PATIENT_ID,
    encountered_at: "2024-06-15T00:00:00Z",
    clinician_id: "00000000-0000-0000-0000-000000000001",
    created_at: "2024-06-15T09:00:00Z",
  },
  {
    id: ENCOUNTER_ID_2,
    patient_id: PATIENT_ID,
    encountered_at: "2024-03-10T00:00:00Z",
    clinician_id: "00000000-0000-0000-0000-000000000001",
    created_at: "2024-03-10T09:00:00Z",
  },
];

const DEFAULT_CREATE_ENCOUNTER = {
  status: "idle" as const,
  lastCreated: null,
  error: null,
  submit: vi.fn(),
  reset: vi.fn(),
};

/** Next.js 15 の async params を模倣する */
function makeParams(): Promise<{ patientId: string }> {
  return Promise.resolve({ patientId: PATIENT_ID });
}

/** await act でラップして Promise を flush する */
async function renderPage() {
  await act(async () => {
    render(<PatientDetailPage params={makeParams()} />);
  });
}

describe("PatientDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseCreateEncounter.mockReturnValue({ ...DEFAULT_CREATE_ENCOUNTER });
  });

  it("loading 状態: 読み込み中テキストが表示される", async () => {
    mockUsePatientDetail.mockReturnValue({
      status: "loading",
      patient: null,
      encounters: [],
      error: null,
      load: vi.fn(),
    });

    await renderPage();
    expect(screen.getByText("読み込み中…")).toBeInTheDocument();
  });

  it("idle 状態: 読み込み中テキストが表示される", async () => {
    mockUsePatientDetail.mockReturnValue({
      status: "idle",
      patient: null,
      encounters: [],
      error: null,
      load: vi.fn(),
    });

    await renderPage();
    expect(screen.getByText("読み込み中…")).toBeInTheDocument();
  });

  it("not_found 状態: 患者が見つかりませんメッセージが表示される", async () => {
    mockUsePatientDetail.mockReturnValue({
      status: "not_found",
      patient: null,
      encounters: [],
      error: null,
      load: vi.fn(),
    });

    await renderPage();
    expect(screen.getByText("患者が見つかりません")).toBeInTheDocument();
  });

  it("error 状態: エラーメッセージが role=alert で表示される", async () => {
    mockUsePatientDetail.mockReturnValue({
      status: "error",
      patient: null,
      encounters: [],
      error: "患者情報の取得に失敗しました。",
      load: vi.fn(),
    });

    await renderPage();
    expect(screen.getByRole("alert")).toHaveTextContent("患者情報の取得に失敗しました");
  });

  it("loaded 状態: 患者カードの各フィールドが表示される", async () => {
    mockUsePatientDetail.mockReturnValue({
      status: "loaded",
      patient: FAKE_PATIENT,
      encounters: [],
      error: null,
      load: vi.fn(),
    });

    await renderPage();
    expect(screen.getByText("山田 太郎")).toBeInTheDocument();
    expect(screen.getByText("MRN-TEST-001")).toBeInTheDocument();
    expect(screen.getByText("1990-01-01")).toBeInTheDocument();
  });

  it("loaded 状態: 受診一覧が Link で表示され href が正しい", async () => {
    mockUsePatientDetail.mockReturnValue({
      status: "loaded",
      patient: FAKE_PATIENT,
      encounters: FAKE_ENCOUNTERS,
      error: null,
      load: vi.fn(),
    });

    await renderPage();

    // 各受診が link として表示される
    const links = screen.getAllByRole("link");
    const encounterLinks = links.filter((l) => l.getAttribute("href")?.startsWith("/encounters/"));
    expect(encounterLinks).toHaveLength(2);
    expect(encounterLinks[0]).toHaveAttribute("href", `/encounters/${ENCOUNTER_ID_1}`);
    expect(encounterLinks[1]).toHaveAttribute("href", `/encounters/${ENCOUNTER_ID_2}`);
  });

  it("フォーム送信: submit が正しい引数で呼ばれる", async () => {
    const mockSubmit = vi.fn();
    mockUsePatientDetail.mockReturnValue({
      status: "loaded",
      patient: FAKE_PATIENT,
      encounters: [],
      error: null,
      load: vi.fn(),
    });
    mockUseCreateEncounter.mockReturnValue({
      ...DEFAULT_CREATE_ENCOUNTER,
      submit: mockSubmit,
    });

    await renderPage();

    const dateInput = screen.getByLabelText("受診日");
    fireEvent.change(dateInput, { target: { value: "2024-07-01" } });

    const submitButton = screen.getByRole("button", { name: "追加" });
    fireEvent.click(submitButton);

    expect(mockSubmit).toHaveBeenCalledWith(PATIENT_ID, "2024-07-01T00:00:00");
  });

  it("送信成功後: 確認メッセージが role=status で表示される", async () => {
    const mockLoad = vi.fn();
    mockUsePatientDetail.mockReturnValue({
      status: "loaded",
      patient: FAKE_PATIENT,
      encounters: [],
      error: null,
      load: mockLoad,
    });
    mockUseCreateEncounter.mockReturnValue({
      ...DEFAULT_CREATE_ENCOUNTER,
      status: "success",
      lastCreated: FAKE_ENCOUNTERS[0],
    });

    await renderPage();
    expect(screen.getByRole("status")).toHaveTextContent("✓ 受診を追加しました");
  });

  it("受診一覧が空の場合: 受診記録がありませんテキストが表示される", async () => {
    mockUsePatientDetail.mockReturnValue({
      status: "loaded",
      patient: FAKE_PATIENT,
      encounters: [],
      error: null,
      load: vi.fn(),
    });

    await renderPage();
    expect(screen.getByText("受診記録がありません")).toBeInTheDocument();
  });

  it("受診エラー時: エラーメッセージが表示される", async () => {
    mockUsePatientDetail.mockReturnValue({
      status: "loaded",
      patient: FAKE_PATIENT,
      encounters: [],
      error: null,
      load: vi.fn(),
    });
    mockUseCreateEncounter.mockReturnValue({
      ...DEFAULT_CREATE_ENCOUNTER,
      status: "error",
      error: "受診の作成に失敗しました。時間をおいて再試行してください。",
    });

    await renderPage();
    expect(screen.getByRole("alert")).toHaveTextContent("受診の作成に失敗しました");
  });

  it("受診一覧の href が /encounters/{enc.id} 形式になっている", async () => {
    mockUsePatientDetail.mockReturnValue({
      status: "loaded",
      patient: FAKE_PATIENT,
      encounters: FAKE_ENCOUNTERS,
      error: null,
      load: vi.fn(),
    });

    await renderPage();

    // 受診一覧内のリンクのみ確認する
    await waitFor(() => {
      const enc1Link = screen
        .getAllByRole("link")
        .find((l) => l.getAttribute("href") === `/encounters/${ENCOUNTER_ID_1}`);
      expect(enc1Link).toBeDefined();
    });
  });
});
