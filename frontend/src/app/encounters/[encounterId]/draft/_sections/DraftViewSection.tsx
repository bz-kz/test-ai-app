/**
 * AI 下書きが生成済み・編集モードに入る前の表示セクション。
 * SOAP 本文 + ConfidencePill + 再生成/編集/承認 の 3 アクションボタン
 * (固定順序 per frontend/SPEC.md#ai-output-patterns) を描画する。
 * 親が `status === "success"` かつ `lifecycle.mode === "view"` のみレンダリングする。
 */
import Button from "@/components/atoms/Button";
import RefreshIcon from "@/components/atoms/icons/RefreshIcon";
import PencilIcon from "@/components/atoms/icons/PencilIcon";
import CheckIcon from "@/components/atoms/icons/CheckIcon";
import AIIndicatedText from "@/components/molecules/AIIndicatedText";
import ConfidencePill from "@/components/molecules/ConfidencePill";
import type { UseDraftLifecycleReturn } from "@/hooks/useDraftLifecycle";
import type { RecordDraft } from "@/types/recordDraft";

export interface DraftViewSectionProps {
  draft: RecordDraft;
  lifecycle: UseDraftLifecycleReturn;
  onRegenerate: () => void;
}

export default function DraftViewSection({
  draft,
  lifecycle,
  onRegenerate,
}: DraftViewSectionProps) {
  return (
    <div>
      {/* ConfidencePill — confidence ≤ 0.5 のとき warning バリアント */}
      {draft.confidence !== null && (
        <div className="mb-3">
          <ConfidencePill confidence={draft.confidence} />
        </div>
      )}

      <AIIndicatedText>
        {/* SOAP 形式の改行を段落として表示する */}
        <pre className="whitespace-pre-wrap font-body text-sm text-navy">{draft.content}</pre>
      </AIIndicatedText>

      {/* アクションボタン: 再生成 / 編集 / 承認 (固定順序 per frontend/SPEC.md#ai-output-patterns) */}
      <div className="mt-4 flex items-center gap-3">
        {/* 再生成 — FE-008 のストリーミングパスで再実行する */}
        <Button variant="secondary" size="sm" onClick={onRegenerate}>
          <RefreshIcon />
          再生成
        </Button>

        {/* 編集 — lifecycle.enterEditMode() を呼び出す */}
        <Button variant="ghost" size="sm" onClick={lifecycle.enterEditMode}>
          <PencilIcon />
          編集
        </Button>

        {/* 承認 — lifecycle.approve() を呼び出す */}
        <Button
          variant="primary"
          size="sm"
          loading={lifecycle.status === "finalizing"}
          disabled={lifecycle.status === "finalizing"}
          onClick={() => void lifecycle.approve()}
        >
          <CheckIcon />
          承認
        </Button>
      </div>

      {/* 承認エラーメッセージ */}
      {lifecycle.status === "error" && lifecycle.error !== null && (
        <p className="mt-3 text-sm text-error" role="alert">
          {lifecycle.error}
        </p>
      )}
    </div>
  );
}
