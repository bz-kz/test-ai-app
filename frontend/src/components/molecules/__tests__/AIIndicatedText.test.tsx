import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import AIIndicatedText from "../AIIndicatedText";

describe("AIIndicatedText molecule", () => {
  it("renders the AI indicator label with default 'AI 生成'", () => {
    render(<AIIndicatedText>テスト本文</AIIndicatedText>);
    expect(screen.getByText("AI 生成")).toBeInTheDocument();
  });

  it("renders a custom label when provided", () => {
    render(<AIIndicatedText label="カスタムラベル">本文</AIIndicatedText>);
    expect(screen.getByText("カスタムラベル")).toBeInTheDocument();
  });

  it("renders the body text as children", () => {
    render(<AIIndicatedText>SOAP ドラフト内容</AIIndicatedText>);
    expect(screen.getByText("SOAP ドラフト内容")).toBeInTheDocument();
  });

  it("has accessible name 'AI 生成テキスト' via role=article + aria-label", () => {
    render(<AIIndicatedText>本文</AIIndicatedText>);
    expect(screen.getByRole("article", { name: "AI 生成テキスト" })).toBeInTheDocument();
  });

  it("custom label does not override the aria-label on the article", () => {
    render(<AIIndicatedText label="別ラベル">本文</AIIndicatedText>);
    // role=article の aria-label は常に "AI 生成テキスト" で固定
    expect(screen.getByRole("article", { name: "AI 生成テキスト" })).toBeInTheDocument();
  });

  it("body text is rendered via React children (not injected as raw HTML)", () => {
    // children に HTML タグ文字列を渡してもエスケープされ、DOM には挿入されない
    render(<AIIndicatedText>{"<script>alert('xss')</script>"}</AIIndicatedText>);
    // <script> 要素が実際に挿入されていないことを確認
    expect(document.querySelector("script")).toBeNull();
    // テキストとして存在していること
    expect(screen.getByText("<script>alert('xss')</script>")).toBeInTheDocument();
  });

  it("renders the left border class for AI indicator", () => {
    render(<AIIndicatedText>本文</AIIndicatedText>);
    const article = screen.getByRole("article");
    expect(article.className).toMatch(/border-l-4/);
  });
});
