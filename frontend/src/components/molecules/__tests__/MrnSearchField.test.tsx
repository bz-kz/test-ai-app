import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import MrnSearchField from "../MrnSearchField";
import type { MrnSearchStatus } from "@/hooks/useMrnSearch";

describe("MrnSearchField molecule", () => {
  it("renders the Japanese label", () => {
    render(<MrnSearchField query="" onQueryChange={vi.fn()} status="idle" />);
    expect(screen.getByLabelText("診察番号 (MRN)")).toBeInTheDocument();
  });

  it("typing into the input fires onQueryChange", async () => {
    const user = userEvent.setup();
    const handler = vi.fn();
    render(<MrnSearchField query="" onQueryChange={handler} status="idle" />);
    await user.type(screen.getByLabelText("診察番号 (MRN)"), "M");
    expect(handler).toHaveBeenCalled();
  });

  it("button is not in loading state when status is idle", () => {
    render(<MrnSearchField query="" onQueryChange={vi.fn()} status="idle" />);
    const btn = screen.getByRole("button", { name: "検索" });
    expect(btn).not.toHaveAttribute("aria-busy", "true");
    expect(btn).not.toBeDisabled();
  });

  it("button reflects loading state when status is searching", () => {
    render(<MrnSearchField query="MRN-001" onQueryChange={vi.fn()} status="searching" />);
    const btn = screen.getByRole("button", { name: "検索中" });
    expect(btn).toHaveAttribute("aria-busy", "true");
    expect(btn).toBeDisabled();
  });

  it("error string is shown and aria-describedby is set on input", () => {
    render(
      <MrnSearchField
        query=""
        onQueryChange={vi.fn()}
        status={"error" as MrnSearchStatus}
        error="検索に失敗しました"
      />
    );
    expect(screen.getByText("検索に失敗しました")).toBeInTheDocument();
    const input = screen.getByLabelText("診察番号 (MRN)");
    expect(input).toHaveAttribute("aria-describedby", "mrn-search-input-desc");
  });

  it("no aria-describedby on input when no error", () => {
    render(<MrnSearchField query="" onQueryChange={vi.fn()} status="idle" />);
    const input = screen.getByLabelText("診察番号 (MRN)");
    expect(input).not.toHaveAttribute("aria-describedby");
  });
});
