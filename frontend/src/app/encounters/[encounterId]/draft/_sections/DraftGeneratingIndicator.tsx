/**
 * 生成中のレイテンシ UX 階層 (skeleton / hint / cancel) を表示するセクション。
 * 親 (DraftPage) が `lifecycle.mode !== "finalized"` かつ `isGenerating` 中のみレンダリングする。
 * frontend/SPEC.md#latency-ux-budget の段階表示を本コンポーネントに集約する。
 *
 * INF-006: CPU 推論で完走に 4-5 分かかるため、hint tier に
 *   - 経過時間 (人間可読 e.g. "1分5秒")
 *   - 目安所要時間文言 ("通常 3-5 分かかります")
 *   - 進捗バー (DRAFT_GENERATION_ETA_MS を 100% とする)
 * を追加して「停止していない」ことを伝える。
 */
import Button from "@/components/atoms/Button";
import Cursor from "@/components/atoms/Cursor";
import AIIndicatedText from "@/components/molecules/AIIndicatedText";
import {
  LATENCY_SKELETON_MS,
  LATENCY_HINT_MS,
  LATENCY_CANCEL_MS,
  DRAFT_GENERATION_ETA_MS,
} from "@/lib/constants";

export interface DraftGeneratingIndicatorProps {
  isStreaming: boolean;
  streamingText: string;
  elapsedMs: number;
  onCancel: () => void;
}

/** ミリ秒を「X分Y秒」形式 (1 分未満なら「Y秒」) に整形する。PHI 非依存。 */
function formatElapsed(ms: number): string {
  const totalSec = Math.max(0, Math.floor(ms / 1000));
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  if (min === 0) return `${sec}秒`;
  return `${min}分${sec}秒`;
}

export default function DraftGeneratingIndicator({
  isStreaming,
  streamingText,
  elapsedMs,
  onCancel,
}: DraftGeneratingIndicatorProps) {
  // 240,000ms を 100% とする進捗率 (上限 100, 下限 0)。
  // 5 分を超えても 100% で頭打ち — ユーザを誤誘導しない。
  const progressPct = Math.min(100, Math.max(0, (elapsedMs / DRAFT_GENERATION_ETA_MS) * 100));
  const progressPctInt = Math.floor(progressPct);

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

          {/* 3000ms 以上: ヒントテキスト + 進捗バー (INF-006) */}
          {elapsedMs >= LATENCY_HINT_MS && (
            <div className="mt-3 space-y-2">
              <p className="text-sm text-slate">
                生成中 (経過 {formatElapsed(elapsedMs)} / 通常 3-5 分かかります)
              </p>
              <div
                className="h-2 w-full overflow-hidden rounded bg-slate-100"
                role="progressbar"
                aria-label="生成進捗 (目安)"
                aria-valuenow={progressPctInt}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div
                  className="h-full bg-navy transition-[width] duration-200"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
              <p className="text-xs text-slate">だいたい {progressPctInt}%</p>
            </div>
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
