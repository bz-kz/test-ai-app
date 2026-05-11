import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import TextArea from "../TextArea";

describe("TextArea atom", () => {
  it("renders a <textarea> element", () => {
    render(<TextArea aria-label="テスト" />);
    const el = screen.getByRole("textbox");
    expect(el.tagName).toBe("TEXTAREA");
  });

  it("defaults to rows=6", () => {
    render(<TextArea aria-label="テスト" />);
    expect(screen.getByRole("textbox")).toHaveAttribute("rows", "6");
  });

  it("rows prop is overridable", () => {
    render(<TextArea aria-label="テスト" rows={4} />);
    expect(screen.getByRole("textbox")).toHaveAttribute("rows", "4");
  });

  it("disabled prop applies disabled attribute", () => {
    render(<TextArea aria-label="テスト" disabled />);
    expect(screen.getByRole("textbox")).toBeDisabled();
  });

  it("disabled prop adds disabled opacity class", () => {
    render(<TextArea aria-label="テスト" disabled />);
    expect(screen.getByRole("textbox").className).toMatch(/disabled:opacity-40/);
  });

  it("error=true adds border-error class and aria-invalid", () => {
    render(<TextArea aria-label="テスト" error />);
    const el = screen.getByRole("textbox");
    expect(el).toHaveAttribute("aria-invalid", "true");
    expect(el.className).toMatch(/border-error/);
  });

  it("error=false does not set aria-invalid", () => {
    render(<TextArea aria-label="テスト" error={false} />);
    expect(screen.getByRole("textbox")).not.toHaveAttribute("aria-invalid");
  });

  it("forwards onChange and value (controlled)", async () => {
    const user = userEvent.setup();
    const handler = vi.fn();
    render(<TextArea aria-label="テスト" value="" onChange={handler} />);
    await user.type(screen.getByRole("textbox"), "a");
    expect(handler).toHaveBeenCalled();
  });

  it("forwards ref to the underlying textarea element", () => {
    const ref = { current: null as HTMLTextAreaElement | null };
    render(<TextArea aria-label="テスト" ref={ref} />);
    expect(ref.current).not.toBeNull();
    expect(ref.current?.tagName).toBe("TEXTAREA");
  });
});
