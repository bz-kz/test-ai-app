/**
 * 確定済みカルテ表示 + 訂正フローを内包するセクション。
 * 「確定済み」バッジを共通ヘッダーとして描き、その下に view / correcting の
 * いずれかを描く。親は `lifecycle.mode === "finalized" && currentFinal !== null`
 * の条件下のみレンダリングする。
 */
import Button from "@/components/atoms/Button";
import TextArea from "@/components/atoms/TextArea";
import LockIcon from "@/components/atoms/icons/LockIcon";
import PencilIcon from "@/components/atoms/icons/PencilIcon";
import FormField from "@/components/molecules/FormField";
import AIIndicatedText from "@/components/molecules/AIIndicatedText";
import ConfidencePill from "@/components/molecules/ConfidencePill";
import ChainList from "@/components/molecules/ChainList";
import type { UseCorrectFinalReturn } from "@/hooks/useCorrectFinal";
import type { UseFinalChainReturn } from "@/hooks/useFinalChain";
import type { RecordFinal } from "@/types/recordFinal";

export interface DraftFinalizedSectionProps {
  currentFinal: RecordFinal;
  correction: UseCorrectFinalReturn;
  finalChain: UseFinalChainReturn;
}

export default function DraftFinalizedSection({
  currentFinal,
  correction,
  finalChain,
}: DraftFinalizedSectionProps) {
  return (
    <div>
      {/* 確定済みバッジ — 不変性を示す視覚的キュー */}
      <div className="mb-4 flex items-center gap-2">
        <span
          className="inline-flex items-center gap-1.5 rounded-sm bg-success/10 px-3 py-1 text-xs font-medium text-[#16A34A]"
          role="status"
          aria-label="確定済みカルテ"
        >
          <LockIcon />
          確定済み
        </span>
      </div>

      {/* 訂正モード: TextArea + キャンセル / 更新ボタン */}
      {correction.mode === "correcting" && (
        <div>
          <FormField id="correct-content" label="訂正内容">
            <TextArea
              id="correct-content"
              value={correction.content}
              onChange={(e) => correction.setContent(e.target.value)}
              rows={8}
              disabled={correction.status === "submitting"}
            />
          </FormField>

          <div className="mt-4 flex items-center gap-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={correction.cancel}
              disabled={correction.status === "submitting"}
            >
              キャンセル
            </Button>

            <Button
              variant="primary"
              size="sm"
              loading={correction.status === "submitting"}
              disabled={correction.status === "submitting" || correction.content.trim() === ""}
              onClick={() => void correction.submit()}
            >
              更新
            </Button>
          </div>

          {/* 訂正エラーメッセージ */}
          {correction.status === "error" && correction.error !== null && (
            <p className="mt-3 text-sm text-error" role="alert">
              {correction.error}
            </p>
          )}
        </div>
      )}

      {/* view モード: 確定カルテ本文 + 訂正ボタン */}
      {correction.mode === "view" && (
        <div>
          {/* confidence が設定されている場合は ConfidencePill を表示する */}
          {currentFinal.confidence !== null && (
            <div className="mb-3">
              <ConfidencePill confidence={currentFinal.confidence} />
            </div>
          )}

          {/* 確定カルテ本文 — ariaLabel で "確定カルテ" とアナウンスする (FE-005 fix #1) */}
          <AIIndicatedText label="確定カルテ" ariaLabel="確定カルテ">
            <pre className="whitespace-pre-wrap font-body text-sm text-navy">
              {currentFinal.content}
            </pre>
          </AIIndicatedText>

          {/* 訂正ボタン */}
          <div className="mt-4">
            <Button variant="secondary" size="sm" onClick={correction.enter}>
              <PencilIcon />
              訂正
            </Button>
          </div>

          {/* FE-006: 訂正履歴チェーン */}
          {finalChain.status === "loading" && (
            <p className="mt-4 text-sm text-slate">訂正履歴を読み込み中…</p>
          )}
          {(finalChain.status === "error" || finalChain.status === "not_found") && (
            <p className="mt-4 text-sm text-slate">訂正履歴を取得できませんでした。</p>
          )}
          {finalChain.status === "loaded" && <ChainList chain={finalChain.chain} />}
        </div>
      )}
    </div>
  );
}
