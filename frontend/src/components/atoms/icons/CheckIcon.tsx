/**
 * 承認 (チェック) アイコン — 14×14 インライン SVG。
 * `currentColor` をストロークに使うため、親の text-* クラスで色を制御する。
 */
export default function CheckIcon() {
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
        d="M2 7l3.5 3.5L12 4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
