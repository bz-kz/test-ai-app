/**
 * ConfidencePill molecule — DESIGN.md §AI Output Patterns
 *
 * AI 信頼度スコアを小さなピルバッジとして表示する。
 * confidence が null の場合は何も表示しない (return null)。
 * confidence ≤ 0.5 の場合は warning バリアント (黄色)、
 * それより大きい場合は neutral バリアント (スレートグレー)。
 *
 * アクセシビリティ:
 * - aria-label で "AI 信頼度 {value}" をスクリーンリーダーに提供する。
 */
import React from "react";

export interface ConfidencePillProps {
  /** 信頼度スコア (0.0〜1.0)。null の場合は何も表示しない。 */
  confidence: number | null;
  /**
   * バリアント。明示的に渡すか、confidence の値から自動で決定される。
   * 渡さない場合は confidence ≤ 0.5 → "warning"、> 0.5 → "neutral"。
   */
  variant?: "warning" | "neutral";
}

/**
 * ConfidencePill molecule。
 *
 * DESIGN.md の Chip §Status Warning / Status 系 Tailwind トークンを使用する:
 *   warning: bg-warning/10 (EAB308 10%) + text-warning-on-bg (#CA8A04)
 *   neutral: bg-slate-100 + text-slate-600
 */
export function ConfidencePill({ confidence, variant }: ConfidencePillProps) {
  // confidence が null の場合は非表示 — プレースホルダーも不要なため null を返す
  if (confidence === null) return null;

  // variant が明示されていない場合は信頼度スコアから自動決定する
  const resolvedVariant = variant ?? (confidence <= 0.5 ? "warning" : "neutral");

  const pillClasses =
    resolvedVariant === "warning"
      ? /* DESIGN.md §Chips §Status Warning: bg #EAB30815, text #CA8A04 */
        "bg-warning/10 text-[#CA8A04]"
      : /* neutral: スレートグレー */
        "bg-slate-100 text-slate-600";

  // 小数点以下 2 桁に丸める (Math.round で浮動小数点誤差を吸収)
  const rounded = Math.round(confidence * 100) / 100;
  const label = `信頼度 ${rounded.toFixed(2)}`;

  return (
    <span
      role="status"
      aria-label={`AI 信頼度 ${rounded.toFixed(2)}`}
      className={[
        /* DESIGN.md §Chips §padding: 4px 12px, radius 4px, 12px/500 uppercase */
        "inline-flex items-center px-3 py-1",
        "rounded-sm text-xs font-medium",
        pillClasses,
      ].join(" ")}
    >
      {label}
    </span>
  );
}

export default ConfidencePill;
