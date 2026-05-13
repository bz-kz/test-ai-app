/**
 * ChainList molecule — 確定カルテ訂正チェーン表示 (FE-006)。
 *
 * DESIGN.md §Lists パターンに基づき ordered list (<ol>) で版を列挙する。
 * - chain は oldest → newest 順 (バックエンド BE-008 の契約)
 * - 現在の chain head (最終エントリ) は視覚的に強調する
 * - 本文冒頭 80 文字 + 省略記号でプレビューを表示する (PHI 表示は operational read)
 * - 内容は React text children として描画する (生 HTML 注入なし)
 * - PHI を console.* に出力しない
 */
import React from "react";
import type { RecordFinal } from "@/types/recordFinal";
import { formatJpDateTimeCompact } from "@/lib/dateFormat";

export interface ChainListProps {
  /** 訂正チェーン — oldest → newest 順 */
  chain: RecordFinal[];
  /** セクションラベル。デフォルト "訂正履歴" */
  label?: string;
}

/**
 * content の冒頭 maxLen 文字を返す。
 * maxLen を超える場合は "…" を付与する。
 * PHI (content) はこの関数内でログに出力しない。
 */
function excerpt(content: string, maxLen: number = 80): string {
  if (content.length <= maxLen) return content;
  return content.slice(0, maxLen) + "…";
}

/**
 * ChainList molecule。
 *
 * chain が空の場合はセクション自体を描画しない。
 * 呼び出し元はステータスに応じてプレースホルダーを表示する責務を持つ。
 */
export function ChainList({ chain, label = "訂正履歴" }: ChainListProps) {
  if (chain.length === 0) {
    return null;
  }

  const lastIndex = chain.length - 1;

  return (
    <section aria-label={label} className="mt-6">
      <h2 className="mb-3 text-sm font-semibold text-slate">{label}</h2>
      <ol className="space-y-2">
        {chain.map((entry, index) => {
          const isHead = index === lastIndex;
          const entryExcerpt = excerpt(entry.content);
          const formattedDate = formatJpDateTimeCompact(entry.created_at);
          const version = index + 1;
          const ariaLabel = `第${version}版 (確定: ${formattedDate}) ${entryExcerpt}`;

          return (
            <li
              key={entry.id}
              aria-label={ariaLabel}
              className={[
                "rounded border border-slate-100 px-3 py-2 text-sm",
                isHead ? "font-bold text-navy bg-slate-50" : "font-normal text-slate bg-white",
              ].join(" ")}
            >
              {/* 版番号 + 確定日時 */}
              <span className="mr-2 text-xs text-slate opacity-70">
                第{version}版 — {formattedDate}
              </span>
              {/* 本文抜粋 — React text node としてエスケープは React が保証する */}
              <span>{entryExcerpt}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

export default ChainList;
