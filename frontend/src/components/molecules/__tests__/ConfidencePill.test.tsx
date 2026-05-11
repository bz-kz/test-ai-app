import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import ConfidencePill from "../ConfidencePill";

describe("ConfidencePill molecule", () => {
  it("confidence が null のとき何もレンダリングしない", () => {
    const { container } = render(<ConfidencePill confidence={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("confidence 0.3 のとき '信頼度 0.30' とレンダリングされる", () => {
    render(<ConfidencePill confidence={0.3} />);
    expect(screen.getByText("信頼度 0.30")).toBeInTheDocument();
  });

  it("confidence 0.3 のとき warning バリアントが適用される", () => {
    render(<ConfidencePill confidence={0.3} />);
    const pill = screen.getByRole("status");
    // warning バリアントのクラスが含まれていること
    expect(pill.className).toMatch(/bg-warning\/10/);
  });

  it("confidence 0.8 のとき neutral バリアントが適用される", () => {
    render(<ConfidencePill confidence={0.8} />);
    const pill = screen.getByRole("status");
    // neutral バリアントのクラスが含まれていること
    expect(pill.className).toMatch(/bg-slate-100/);
  });

  it("confidence 0.5 のとき warning バリアントが適用される (境界値 ≤ 0.5 は warning)", () => {
    render(<ConfidencePill confidence={0.5} />);
    const pill = screen.getByRole("status");
    expect(pill.className).toMatch(/bg-warning\/10/);
  });

  it("confidence 0.51 のとき neutral バリアントが適用される", () => {
    render(<ConfidencePill confidence={0.51} />);
    const pill = screen.getByRole("status");
    expect(pill.className).toMatch(/bg-slate-100/);
  });

  it("aria-label が 'AI 信頼度 {value}' になっている", () => {
    render(<ConfidencePill confidence={0.42} />);
    const pill = screen.getByRole("status", { name: "AI 信頼度 0.42" });
    expect(pill).toBeInTheDocument();
  });

  it("confidence 0.8 のとき '信頼度 0.80' と 2 桁表示される", () => {
    render(<ConfidencePill confidence={0.8} />);
    expect(screen.getByText("信頼度 0.80")).toBeInTheDocument();
  });

  it("variant='warning' を明示した場合は confidence > 0.5 でも warning バリアントが適用される", () => {
    render(<ConfidencePill confidence={0.9} variant="warning" />);
    const pill = screen.getByRole("status");
    expect(pill.className).toMatch(/bg-warning\/10/);
  });

  it("variant='neutral' を明示した場合は confidence ≤ 0.5 でも neutral バリアントが適用される", () => {
    render(<ConfidencePill confidence={0.3} variant="neutral" />);
    const pill = screen.getByRole("status");
    expect(pill.className).toMatch(/bg-slate-100/);
  });
});
