import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import Button from "../Button";

describe("Button atom", () => {
  it("renders a native button element", () => {
    render(<Button>クリック</Button>);
    const el = screen.getByRole("button");
    expect(el.tagName).toBe("BUTTON");
  });

  it("default variant is primary", () => {
    render(<Button>保存</Button>);
    expect(screen.getByRole("button")).toHaveAttribute("data-variant", "primary");
  });

  it("variant prop changes data-variant attribute", () => {
    const variants = ["secondary", "ghost", "destructive"] as const;
    for (const variant of variants) {
      const { unmount } = render(<Button variant={variant}>テスト</Button>);
      expect(screen.getByRole("button")).toHaveAttribute("data-variant", variant);
      unmount();
    }
  });

  it("disabled prop applies the disabled attribute and prevents onClick", async () => {
    const user = userEvent.setup();
    const handler = vi.fn();
    render(
      <Button disabled onClick={handler}>
        保存
      </Button>
    );
    const btn = screen.getByRole("button");
    expect(btn).toBeDisabled();
    await user.click(btn);
    expect(handler).not.toHaveBeenCalled();
  });

  it("loading prop sets aria-busy and prevents onClick", async () => {
    const user = userEvent.setup();
    const handler = vi.fn();
    render(
      <Button loading onClick={handler}>
        保存
      </Button>
    );
    const btn = screen.getByRole("button");
    expect(btn).toHaveAttribute("aria-busy", "true");
    expect(btn).toBeDisabled();
    await user.click(btn);
    expect(handler).not.toHaveBeenCalled();
  });

  it("keyboard activation: Enter and Space trigger onClick", async () => {
    const user = userEvent.setup();
    const handler = vi.fn();
    render(<Button onClick={handler}>保存</Button>);
    const btn = screen.getByRole("button");
    btn.focus();
    await user.keyboard("{Enter}");
    await user.keyboard(" ");
    expect(handler).toHaveBeenCalledTimes(2);
  });

  it("accessible name from children", () => {
    render(<Button>保存</Button>);
    expect(screen.getByRole("button", { name: "保存" })).toBeInTheDocument();
  });
});
