/**
 * FormField molecule — DESIGN.md §Inputs
 *
 * label + 子インプットスロット + helper/error テキストを組み合わせる分子。
 * Input atom の accessible name はこの label の htmlFor 経由で提供される。
 *
 * 注意: error が指定された場合、消費側は Input に `error={!!error}` を渡す責任がある。
 * このコンポーネントは子を mutate しない。
 */
import React from "react";

export interface FormFieldProps {
  /** input の id と label の htmlFor を一致させるための ID */
  id: string;
  /** ラベルテキスト */
  label: string;
  /** ヘルパーテキスト (error が指定された場合は表示されない) */
  helper?: string;
  /** エラーメッセージ (指定された場合は helper の代わりに error 色で表示) */
  error?: string;
  /** Input atom などの子要素 */
  children: React.ReactNode;
}

/**
 * FormField molecule。
 *
 * アクセシビリティ:
 * - <label htmlFor={id}> が子の input と関連付けられる。
 * - error テキストは aria-describedby で入力欄と結びつける。
 *   消費側は子 Input に `aria-describedby={id + "-desc"}` を渡す必要がある。
 */
export function FormField({ id, label, helper, error, children }: FormFieldProps) {
  const descId = `${id}-desc`;
  const hasDesc = Boolean(error ?? helper);

  return (
    <div className="flex flex-col gap-1.5">
      {/* DESIGN.md §Inputs: label — DM Sans 14px/500, color navy, bottom margin 6px */}
      <label htmlFor={id} className="text-sm font-medium text-navy">
        {label}
      </label>

      {children}

      {hasDesc && (
        <p id={descId} role="status" className={`text-xs ${error ? "text-error" : "text-slate"}`}>
          {error ?? helper}
        </p>
      )}
    </div>
  );
}

export default FormField;
