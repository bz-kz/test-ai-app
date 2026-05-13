/**
 * 錠前アイコン (確定済みバッジ用) — 14×14 インライン SVG。
 * `currentColor` をストロークに使うため、親の text-* クラスで色を制御する。
 */
export default function LockIcon() {
  return (
    <svg
      width={14}
      height={14}
      viewBox="0 0 14 14"
      fill="none"
      aria-hidden="true"
      className="shrink-0"
    >
      <rect x="2.5" y="6.5" width="9" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M4.5 6.5V4.5a2.5 2.5 0 0 1 5 0v2"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
