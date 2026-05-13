/**
 * 編集 (鉛筆) アイコン — 14×14 インライン SVG。
 * `currentColor` をストロークに使うため、親の text-* クラスで色を制御する。
 */
export default function PencilIcon() {
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
        d="M9.5 2.5l2 2-7 7H2.5v-2l7-7z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
