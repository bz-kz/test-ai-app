import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import RecordButton from "../RecordButton";

describe("RecordButton atom", () => {
  // --- 状態別レンダリング ---

  it("idle 状態: aria-pressed=false、デフォルト aria-label が '録音を開始'", () => {
    render(<RecordButton state="idle" onClick={vi.fn()} />);
    const btn = screen.getByRole("button");
    expect(btn).toHaveAttribute("aria-pressed", "false");
    expect(btn).toHaveAccessibleName("録音を開始");
  });

  it("recording 状態: aria-pressed=true、デフォルト aria-label が '録音を停止'", () => {
    render(<RecordButton state="recording" onClick={vi.fn()} />);
    const btn = screen.getByRole("button");
    expect(btn).toHaveAttribute("aria-pressed", "true");
    expect(btn).toHaveAccessibleName("録音を停止");
  });

  it("uploading 状態: aria-pressed=false、デフォルト aria-label が 'アップロード中'", () => {
    render(<RecordButton state="uploading" onClick={vi.fn()} />);
    const btn = screen.getByRole("button");
    expect(btn).toHaveAttribute("aria-pressed", "false");
    expect(btn).toHaveAccessibleName("アップロード中");
  });

  // --- onClick ---

  it("idle 状態でクリックすると onClick が呼ばれる", async () => {
    const user = userEvent.setup();
    const handler = vi.fn();
    render(<RecordButton state="idle" onClick={handler} />);
    await user.click(screen.getByRole("button"));
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("recording 状態でクリックすると onClick が呼ばれる", async () => {
    const user = userEvent.setup();
    const handler = vi.fn();
    render(<RecordButton state="recording" onClick={handler} />);
    await user.click(screen.getByRole("button"));
    expect(handler).toHaveBeenCalledTimes(1);
  });

  // --- disabled ---

  it("disabled=true のとき button が無効化され onClick は呼ばれない", async () => {
    const user = userEvent.setup();
    const handler = vi.fn();
    render(<RecordButton state="idle" onClick={handler} disabled />);
    const btn = screen.getByRole("button");
    expect(btn).toBeDisabled();
    await user.click(btn);
    expect(handler).not.toHaveBeenCalled();
  });

  // --- aria-label override ---

  it("aria-label prop を渡すとデフォルトラベルが上書きされる", () => {
    render(<RecordButton state="idle" onClick={vi.fn()} aria-label="録音開始カスタム" />);
    expect(screen.getByRole("button")).toHaveAccessibleName("録音開始カスタム");
  });

  // --- キーボードアクセシビリティ ---

  it("Enter / Space でクリックが発火する (キーボードアクセシビリティ)", async () => {
    const user = userEvent.setup();
    const handler = vi.fn();
    render(<RecordButton state="idle" onClick={handler} />);
    const btn = screen.getByRole("button");
    btn.focus();
    await user.keyboard("{Enter}");
    await user.keyboard(" ");
    expect(handler).toHaveBeenCalledTimes(2);
  });
});
