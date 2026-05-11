/**
 * TextArea atom — DESIGN.md §Inputs のテキストエリア版。
 *
 * forwardRef を使用し、親から ref を渡せるようにしている。
 * アクセシブルな名前は消費側の FormField が <label htmlFor> で提供する。
 */
import React from "react";

export interface TextAreaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  /** エラー状態: ボーダーを error 色に変え aria-invalid="true" を設定する */
  error?: boolean;
}

/**
 * TextArea atom。
 *
 * - デフォルト rows=6 (上書き可)。
 * - error={true} でボーダーが error 色になり aria-invalid が設定される。
 * - disabled 時は 40% opacity + disabled カーソル。
 * - フォーカスリングは DESIGN.md §Accessibility Bar に準拠。
 */
const TextArea = React.forwardRef<HTMLTextAreaElement, TextAreaProps>(function TextArea(
  { error = false, disabled = false, className = "", rows = 6, ...rest },
  ref
) {
  const baseClasses = [
    /* DESIGN.md §Inputs: padding 10px 14px, radius 8px */
    "px-[14px] py-[10px]",
    /* DM Sans 14px — body font */
    "text-sm font-body text-navy",
    /* ボーダーと背景 */
    "rounded-[8px] bg-surface",
    /* ホバー */
    "hover:border-navy",
    /* フォーカスリング — DESIGN.md §Accessibility Bar */
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy focus-visible:ring-offset-2",
    /* disabled: 40% opacity */
    "disabled:opacity-40 disabled:cursor-not-allowed disabled:bg-slate-50",
    /* リサイズは垂直方向のみ許可 */
    "resize-y",
    /* 幅は親に委ねる */
    "w-full",
    /* トランジション */
    "transition-colors",
    /* エラー状態とデフォルト状態でボーダー色を切り替える */
    error ? "border-2 border-error" : "border border-slate/30",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <textarea
      ref={ref}
      rows={rows}
      disabled={disabled}
      aria-invalid={error ? "true" : undefined}
      className={baseClasses}
      {...rest}
    />
  );
});

export { TextArea };
export default TextArea;
