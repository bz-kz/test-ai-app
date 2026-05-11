/**
 * Cursor atom — DESIGN.md §Streaming Text
 *
 * ストリーミング中の挿入点を示すキャレットカーソル。
 * - 1px 幅 × 1em 高のインラインブロック
 * - 本文色 (currentColor) を 70% 不透明度で表示
 * - CSS アニメーションで点滅 (prefers-reduced-motion 対応)
 * - aria-hidden="true" — スクリーンリーダーには不要な装飾要素
 */
import React from "react";

/**
 * ストリーミングキャレットカーソル。
 * AIIndicatedText の children 末尾に配置し、isStreaming=false になったら
 * 親コンポーネントが unmount する (非表示にするだけでよい)。
 */
export function Cursor() {
  return (
    <>
      <style>{`
        @keyframes vh-caret-blink {
          0%, 100% { opacity: 0.7; }
          50% { opacity: 0; }
        }
        .vh-caret {
          display: inline-block;
          width: 1px;
          height: 1em;
          background: currentColor;
          opacity: 0.7;
          vertical-align: text-bottom;
          margin-left: 1px;
          animation: vh-caret-blink 1s step-start infinite;
        }
        @media (prefers-reduced-motion: reduce) {
          .vh-caret {
            animation: none;
            opacity: 0.7;
          }
        }
      `}</style>
      <span className="vh-caret" aria-hidden="true" />
    </>
  );
}

export default Cursor;
