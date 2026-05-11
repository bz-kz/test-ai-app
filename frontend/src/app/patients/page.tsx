"use client";

/**
 * /patients ページ — MRN 検索と結果表示。
 *
 * - useMrnSearch フックを使い、MRN 入力に応じて患者を検索する。
 * - PHI (query, result) は console.* に出力しない。
 * - PHI は localStorage / sessionStorage / indexedDB / cookies に書き込まない。
 * - fetch は直接呼び出さない (フック → サービス層に委譲)。
 */
import { useMrnSearch } from "@/hooks/useMrnSearch";
import MrnSearchField from "@/components/molecules/MrnSearchField";

export default function PatientsPage() {
  const { query, setQuery, status, result } = useMrnSearch();

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-6 font-display text-2xl font-bold text-navy">患者検索</h1>

      <form onSubmit={(e) => e.preventDefault()} aria-label="患者検索フォーム">
        <MrnSearchField
          query={query}
          onQueryChange={setQuery}
          status={status}
          error={
            status === "error" ? "検索に失敗しました。時間をおいて再試行してください。" : undefined
          }
        />
      </form>

      <section aria-live="polite" aria-atomic="true" className="mt-8">
        {status === "idle" && (
          <p className="text-center text-slate">MRN を入力すると患者カードが表示されます</p>
        )}

        {status === "found" && result !== null && (
          <div className="rounded-[8px] border border-slate/20 bg-surface p-6 shadow-sm">
            <dl className="space-y-2">
              <div className="flex gap-4">
                <dt className="w-28 text-sm font-medium text-slate">氏名</dt>
                <dd className="text-sm text-navy">
                  {result.family_name} {result.given_name}
                </dd>
              </div>
              <div className="flex gap-4">
                <dt className="w-28 text-sm font-medium text-slate">診察番号</dt>
                <dd className="font-mono text-sm text-navy">{result.mrn}</dd>
              </div>
              <div className="flex gap-4">
                <dt className="w-28 text-sm font-medium text-slate">生年月日</dt>
                <dd className="text-sm text-navy">{result.date_of_birth}</dd>
              </div>
            </dl>
          </div>
        )}

        {status === "not_found" && <p className="text-center text-slate">該当患者なし</p>}

        {status === "error" && (
          <p className="text-center text-error" role="alert">
            検索に失敗しました。時間をおいて再試行してください。
          </p>
        )}
      </section>
    </main>
  );
}
