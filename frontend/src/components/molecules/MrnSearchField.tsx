/**
 * MrnSearchField molecule — 診察番号検索フィールド。
 *
 * FormField + Input + Button を組み合わせたプレゼンテーション専用コンポーネント。
 * サービス/フックは呼び出さない。状態はすべて props 経由で受け取る。
 *
 * UI 文字列はすべて日本語。
 */
import FormField from "@/components/molecules/FormField";
import Input from "@/components/atoms/Input";
import Button from "@/components/atoms/Button";
import type { MrnSearchStatus } from "@/hooks/useMrnSearch";

export interface MrnSearchFieldProps {
  /** 現在の入力値 */
  query: string;
  /** 入力値変更ハンドラ */
  onQueryChange: (next: string) => void;
  /** 検索状態 */
  status: MrnSearchStatus;
  /** エラーメッセージ (status==="error" のときに表示) */
  error?: string;
}

/**
 * MrnSearchField molecule。
 *
 * アクセシビリティ:
 * - Input の accessible name は FormField の label 経由で提供される。
 * - エラー時は aria-describedby で Input とエラーテキストを結びつける。
 */
export function MrnSearchField({ query, onQueryChange, status, error }: MrnSearchFieldProps) {
  const fieldId = "mrn-search-input";
  const isSearching = status === "searching";

  return (
    <div className="flex flex-col gap-3">
      <FormField id={fieldId} label="診察番号 (MRN)" error={error}>
        <div className="flex gap-2">
          <Input
            id={fieldId}
            type="search"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="MRN を入力"
            error={!!error}
            aria-describedby={error ? `${fieldId}-desc` : undefined}
            disabled={isSearching}
          />
          <Button
            type="submit"
            variant="primary"
            size="md"
            loading={isSearching}
            aria-label={isSearching ? "検索中" : "検索"}
          >
            検索
          </Button>
        </div>
      </FormField>
    </div>
  );
}

export default MrnSearchField;
