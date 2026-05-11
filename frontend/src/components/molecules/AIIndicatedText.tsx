/**
 * AIIndicatedText molecule — DESIGN.md §AI Output Patterns
 *
 * AI 生成テキストを視覚的に区別するためのラッパー。
 * - 左 4px の sage ボーダー (Tertiary Sage #059669)
 * - AI アイコン + ラベル "AI 生成" (デフォルト)
 * - body text は React children として受け取る (生 HTML 注入なし)
 *
 * アクセシビリティ:
 * - role="article" + aria-label でスクリーンリーダーに AI 生成ブロックを明示する。
 * - AI アイコンは aria-hidden で装飾扱いとし、ラベルテキストで意味を補完する。
 */
import React from "react";

export interface AIIndicatedTextProps {
  children: React.ReactNode;
  /** AI 生成ラベルキャプション。デフォルト "AI 生成" */
  label?: string;
}

/**
 * AI アイコン — シンプルなインライン SVG (CPU アイコン風のロボット顔)。
 * Heroicons 等がインストールされていないため独自定義。
 * aria-hidden で装飾として扱い、アクセシブルな名前は aria-label に委ねる。
 */
function AIIcon() {
  return (
    <svg
      width={16}
      height={16}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      className="shrink-0"
    >
      {/* ロボット頭部 */}
      <rect x="2" y="4" width="12" height="9" rx="2" stroke="#059669" strokeWidth="1.5" />
      {/* 目 (左) */}
      <circle cx="5.5" cy="8.5" r="1" fill="#059669" />
      {/* 目 (右) */}
      <circle cx="10.5" cy="8.5" r="1" fill="#059669" />
      {/* アンテナ */}
      <line
        x1="8"
        y1="4"
        x2="8"
        y2="1.5"
        stroke="#059669"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <circle cx="8" cy="1" r="0.75" fill="#059669" />
    </svg>
  );
}

/**
 * AIIndicatedText molecule。
 *
 * DESIGN.md の "AI-Generated Indicator" パターンを実装する:
 *   - 3–4px 左ボーダーを Tertiary Sage (#059669) で描画
 *   - AI アイコン + ラベルを先頭に配置
 *   - children をそのまま描画 (エスケープはReact が保証)
 */
export function AIIndicatedText({ children, label = "AI 生成" }: AIIndicatedTextProps) {
  return (
    <div
      role="article"
      aria-label="AI 生成テキスト"
      /* DESIGN.md: 左ボーダー Tertiary Sage (#059669)、背景は周囲に合わせる */
      className="border-l-4 border-[#059669] pl-4"
    >
      {/* AI インジケーター行 */}
      <div className="mb-2 flex items-center gap-1.5">
        <AIIcon />
        <span className="text-xs font-medium text-[#059669]">{label}</span>
      </div>

      {/* 本文 — React children のためエスケープは React が保証する */}
      <div className="text-sm text-navy">{children}</div>
    </div>
  );
}

export default AIIndicatedText;
