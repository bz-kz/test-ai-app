import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import Input from "../Input";

describe("Input atom", () => {
  it("renders an <input> element with default type=text", () => {
    render(<Input aria-label="テスト" />);
    const el = screen.getByRole("textbox");
    expect(el.tagName).toBe("INPUT");
    expect(el).toHaveAttribute("type", "text");
  });

  it("type prop is forwarded", () => {
    render(<Input type="search" aria-label="検索" />);
    expect(screen.getByRole("searchbox")).toHaveAttribute("type", "search");
  });

  it("disabled prop applies disabled attribute", () => {
    render(<Input aria-label="テスト" disabled />);
    expect(screen.getByRole("textbox")).toBeDisabled();
  });

  it("disabled prop adds disabled opacity class", () => {
    render(<Input aria-label="テスト" disabled />);
    expect(screen.getByRole("textbox").className).toMatch(/disabled:opacity-40/);
  });

  it("error=true adds border-error class and aria-invalid", () => {
    render(<Input aria-label="テスト" error />);
    const el = screen.getByRole("textbox");
    expect(el).toHaveAttribute("aria-invalid", "true");
    expect(el.className).toMatch(/border-error/);
  });

  it("error=false does not set aria-invalid", () => {
    render(<Input aria-label="テスト" error={false} />);
    expect(screen.getByRole("textbox")).not.toHaveAttribute("aria-invalid");
  });

  it("forwards onChange and value (controlled)", async () => {
    const user = userEvent.setup();
    const handler = vi.fn();
    render(<Input aria-label="テスト" value="" onChange={handler} />);
    await user.type(screen.getByRole("textbox"), "a");
    expect(handler).toHaveBeenCalled();
  });

  it("forwards ref to the underlying input element", () => {
    const ref = { current: null as HTMLInputElement | null };
    render(<Input aria-label="テスト" ref={ref} />);
    expect(ref.current).not.toBeNull();
    expect(ref.current?.tagName).toBe("INPUT");
  });

  it("forwards arbitrary aria-* props", () => {
    render(<Input aria-label="診察番号" aria-required="true" />);
    const el = screen.getByRole("textbox", { name: "診察番号" });
    expect(el).toHaveAttribute("aria-required", "true");
  });
});
