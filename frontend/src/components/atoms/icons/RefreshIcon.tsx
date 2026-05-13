/**
 * 再生成 (リフレッシュ) アイコン — 14×14 インライン SVG。
 * `currentColor` をストロークに使うため、親の text-* クラスで色を制御する。
 */
export default function RefreshIcon() {
  return (
    <svg
      width={14}
      height={14}
      viewBox="0 0 14 14"
      fill="none"
      aria-hidden="true"
      className="shrink-0"
    >
      <path
        d="M12.5 2.5A6 6 0 1 1 7 1"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path d="M7 1l2 2-2 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
