/**
 * 下書きを臨床医が手で編集中のテキストエリアセクション。
 * 親が `status === "success"` かつ `lifecycle.mode === "editing"` のみレンダリングする。
 */
import Button from "@/components/atoms/Button";
import TextArea from "@/components/atoms/TextArea";
import FormField from "@/components/molecules/FormField";
import type { UseDraftLifecycleReturn } from "@/hooks/useDraftLifecycle";

export interface DraftEditingSectionProps {
  lifecycle: UseDraftLifecycleReturn;
}

export default function DraftEditingSection({ lifecycle }: DraftEditingSectionProps) {
  const isSaving = lifecycle.status === "saving";

  return (
    <div>
      <FormField id="edit-content" label="下書き編集">
        <TextArea
          id="edit-content"
          value={lifecycle.editContent}
          onChange={(e) => lifecycle.setEditContent(e.target.value)}
          rows={8}
          disabled={isSaving}
        />
      </FormField>

      <div className="mt-4 flex items-center gap-3">
        {/* キャンセル */}
        <Button variant="ghost" size="sm" onClick={lifecycle.cancelEdit} disabled={isSaving}>
          キャンセル
        </Button>

        {/* 更新 — editContent が空白のみの場合は無効 */}
        <Button
          variant="primary"
          size="sm"
          loading={isSaving}
          disabled={isSaving || lifecycle.editContent.trim() === ""}
          onClick={() => void lifecycle.saveEdit()}
        >
          更新
        </Button>
      </div>

      {/* 編集エラーメッセージ */}
      {lifecycle.status === "error" && lifecycle.error !== null && (
        <p className="mt-3 text-sm text-error" role="alert">
          {lifecycle.error}
        </p>
      )}
    </div>
  );
}
