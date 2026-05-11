import React from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** DESIGN.md §Buttons — バリアント */
  variant?: ButtonVariant;
  /** DESIGN.md §Buttons §Sizes */
  size?: ButtonSize;
  /** ローディング中はスピナーを表示し、クリックを無効化する */
  loading?: boolean;
  children: React.ReactNode;
}

/* DESIGN.md §Buttons §Variants に対応するクラス */
const variantClasses: Record<ButtonVariant, string> = {
  /* Primary: #0F172A fill / #FFFFFF text / hover: #020617 */
  primary: "bg-navy text-white hover:bg-[#020617]",
  /* Secondary: transparent / #0F172A text / 1px navy border / hover: #0F172A0A */
  secondary: "bg-transparent text-navy border border-navy hover:bg-navy/5",
  /* Ghost: transparent / #475569 text / hover: #F1F5F9 */
  ghost: "bg-transparent text-slate-600 hover:bg-slate-100",
  /* Destructive: #EF4444 fill / #FFFFFF text / hover: #DC2626 */
  destructive: "bg-error text-white hover:bg-[#DC2626]",
};

/* DESIGN.md §Buttons §Sizes に対応するクラス */
const sizeClasses: Record<ButtonSize, string> = {
  /* sm: 6px×14px padding, 14px text, 32px height */
  sm: "px-3.5 py-1.5 text-sm h-8",
  /* md: 10px×22px padding, 14px text, 42px height */
  md: "px-[22px] py-2.5 text-sm h-[42px]",
  /* lg: 12px×28px padding, 16px text, 48px height */
  lg: "px-7 py-3 text-base h-12",
};

/* ローディング中のスピナー — バリアントのテキスト色を継承する */
function Spinner() {
  return (
    <svg
      className="animate-spin"
      width={14}
      height={14}
      viewBox="0 0 14 14"
      fill="none"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="2" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M13 7a6 6 0 0 1-6 6V11a4 4 0 0 0 4-4h2z"
      />
    </svg>
  );
}

/**
 * Button atom — DESIGN.md §Buttons
 *
 * forwardRef を使用し、親から ref を渡せるようにしている。
 * data-variant は自動テストで variant を検証するためのフック。
 */
const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "primary",
    size = "md",
    loading = false,
    disabled = false,
    type = "button",
    children,
    className = "",
    onClick,
    ...rest
  },
  ref
) {
  /* ローディング中はクリックを無効化するため disabled 扱いにする */
  const isDisabled = disabled || loading;

  const baseClasses =
    "inline-flex items-center justify-center gap-2 rounded-[8px] font-medium transition-colors" +
    /* DESIGN.md §Disabled State: 40% opacity */
    " disabled:opacity-40 disabled:cursor-not-allowed disabled:pointer-events-none" +
    /* フォーカスリング — DESIGN.md §Accessibility Bar */
    " focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy focus-visible:ring-offset-2";

  const classes = [baseClasses, variantClasses[variant], sizeClasses[size], className]
    .join(" ")
    .trim();

  return (
    <button
      ref={ref}
      type={type}
      disabled={isDisabled}
      aria-busy={loading ? "true" : undefined}
      data-variant={variant}
      className={classes}
      onClick={onClick}
      {...rest}
    >
      {loading && <Spinner />}
      {children}
    </button>
  );
});

export { Button };
export default Button;
