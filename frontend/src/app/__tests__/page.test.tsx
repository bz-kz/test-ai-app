/**
 * ルートランディングページの基本レンダリングテスト。
 * 静的サーバーコンポーネントなので、見出しと CTA リンクの存在を確認する。
 */
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import HomePage from "../page";

describe("HomePage (FE-012: root landing page)", () => {
  it("renders the h1 heading", () => {
    render(<HomePage />);
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("AI カルテ生成システム");
  });

  it("includes the PHI-safety tagline mentioning ローカル", () => {
    render(<HomePage />);
    expect(screen.getByText(/ローカル LLM による SOAP カルテ下書き生成/)).toBeInTheDocument();
    expect(screen.getByText(/ローカルネットワーク外へ送信しません/)).toBeInTheDocument();
  });

  it("renders the CTA link pointing to /patients", () => {
    render(<HomePage />);
    const link = screen.getByRole("link", { name: "患者検索を開く" });
    expect(link).toHaveAttribute("href", "/patients");
  });

  it("renders the feature list with 4 items", () => {
    render(<HomePage />);
    const list = screen.getByRole("list", { name: "主な機能" });
    const items = list.querySelectorAll("li");
    expect(items).toHaveLength(4);
  });

  it("does not render a second h1 (heading hierarchy)", () => {
    render(<HomePage />);
    const h1s = screen.getAllByRole("heading", { level: 1 });
    expect(h1s).toHaveLength(1);
  });
});
