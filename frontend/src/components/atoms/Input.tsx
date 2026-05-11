/**
 * Input atom — DESIGN.md §Inputs
 *
 * forwardRef を使用し、親から ref を渡せるようにしている。
 * アクセシブルな名前は消費側の FormField が <label htmlFor> で提供する。
 */
import React from "react";

export interface InputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "size"> {
  /** エラー状態: ボーダーを error 色に変え aria-invalid="true" を設定する */
  error?: boolean;
}

/**
 * Input atom。
 *
 * - デフォルト type は "text"。
 * - error={true} でボーダーが error 色になり aria-invalid が設定される。
 * - disabled 時は 40% opacity + disabled カーソル。
 * - フォーカスリングは DESIGN.md §Accessibility Bar に準拠。
 */
const Input = React.forwardRef<HTMLInputElement, InputProps>(function Input(
  { error = false, disabled = false, className = "", type = "text", ...rest },
  ref
) {
  const baseClasses = [
    /* DESIGN.md §Inputs: height 42px, padding 10px 14px, radius 8px */
    "h-[42px] px-[14px] py-[10px]",
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
    <input
      ref={ref}
      type={type}
      disabled={disabled}
      aria-invalid={error ? "true" : undefined}
      className={baseClasses}
      {...rest}
    />
  );
});

export { Input };
export default Input;
