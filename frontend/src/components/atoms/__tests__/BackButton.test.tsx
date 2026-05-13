import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { useRouter } from "next/navigation";
import BackButton from "../BackButton";

describe("BackButton atom", () => {
  it("renders a native button with the default label", () => {
    render(<BackButton />);
    const el = screen.getByRole("button", { name: "← 戻る" });
    expect(el.tagName).toBe("BUTTON");
  });

  it("renders the provided label", () => {
    render(<BackButton label="← 患者検索に戻る" />);
    expect(screen.getByRole("button", { name: "← 患者検索に戻る" })).toBeInTheDocument();
  });

  it("invokes router.back() on click", async () => {
    const user = userEvent.setup();
    const backMock = vi.fn();
    vi.mocked(useRouter).mockReturnValueOnce({
      push: vi.fn(),
      replace: vi.fn(),
      back: backMock,
      forward: vi.fn(),
      refresh: vi.fn(),
      prefetch: vi.fn(),
    } as unknown as ReturnType<typeof useRouter>);

    render(<BackButton />);
    await user.click(screen.getByRole("button"));
    expect(backMock).toHaveBeenCalledTimes(1);
  });
});
