/**
 * 生成中のレイテンシ UX 階層 (skeleton / hint / cancel) を表示するセクション。
 * 親 (DraftPage) が `lifecycle.mode !== "finalized"` かつ `isGenerating` 中のみレンダリングする。
 * frontend/SPEC.md#latency-ux-budget の段階表示を本コンポーネントに集約する。
 */
import Button from "@/components/atoms/Button";
import Cursor from "@/components/atoms/Cursor";
import AIIndicatedText from "@/components/molecules/AIIndicatedText";
import { LATENCY_SKELETON_MS, LATENCY_HINT_MS, LATENCY_CANCEL_MS } from "@/lib/constants";

export interface DraftGeneratingIndicatorProps {
  isStreaming: boolean;
  streamingText: string;
  elapsedMs: number;
  onCancel: () => void;
}

export default function DraftGeneratingIndicator({
  isStreaming,
  streamingText,
  elapsedMs,
  onCancel,
}: DraftGeneratingIndicatorProps) {
  return (
    <div>
      {/* ストリーミング中かつチャンクが届き始めていればテキストを表示する。
          チャンクが届く前はスケルトン階層 (1000ms 以上) でフォールバックする。
          DESIGN.md: ストリーミングテキストの隣にキャレットカーソルを表示する。
          スピナーとキャレットは同時に表示しない。 */}
      {isStreaming && streamingText !== "" ? (
        <AIIndicatedText>
          <pre className="whitespace-pre-wrap font-body text-sm text-navy">
            {streamingText}
            <Cursor />
          </pre>
        </AIIndicatedText>
      ) : (
        <>
          {/* 1000ms 以上: スケルトン (チャンク未到着時のフォールバック) */}
          {elapsedMs >= LATENCY_SKELETON_MS && (
            <div className="space-y-3" role="status" aria-label="生成中">
              <div className="h-4 animate-pulse rounded bg-slate-100" />
              <div className="h-4 w-5/6 animate-pulse rounded bg-slate-100" />
              <div className="h-4 w-4/6 animate-pulse rounded bg-slate-100" />
            </div>
          )}

          {/* 3000ms 以上: ヒントテキスト */}
          {elapsedMs >= LATENCY_HINT_MS && (
            <p className="mt-3 text-sm text-slate">ローカルモデル応答待ち…</p>
          )}
        </>
      )}

      {/* 10000ms 以上: キャンセルボタン (ストリーミング中も表示する) */}
      {elapsedMs >= LATENCY_CANCEL_MS && (
        <div className="mt-4">
          <Button variant="secondary" size="sm" onClick={onCancel}>
            キャンセル
          </Button>
        </div>
      )}
    </div>
  );
}
