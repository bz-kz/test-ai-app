"use client";

/**
 * /encounters/[encounterId] ページ — 受診詳細 + 下書き一覧 + 確定カルテ一覧 (FE-007b)。
 *
 * - useEncounterDetail で受診情報・下書き一覧・確定カルテ一覧を取得する。
 * - PHI (drafts[].content, finals[].content) は console.* に出力しない。
 * - PHI は localStorage / sessionStorage / indexedDB / URL には書き込まない。
 * - fetch は直接呼び出さない (フック → サービス層に委譲)。
 * - clinician_id は最初の 8 文字のみ表示し、PHI 漏洩を防ぐ (表示目的の短縮)。
 */
import React, { useEffect } from "react";
import Link from "next/link";
import { useEncounterDetail } from "@/hooks/useEncounterDetail";
import BackButton from "@/components/atoms/BackButton";
import { formatJpDate, formatJpDateTime } from "@/lib/dateFormat";

type Params = { encounterId: string };

export default function EncounterDetailPage({ params }: { params: Promise<Params> }) {
  const { encounterId } = React.use(params);

  const { status, encounter, drafts, finals, load } = useEncounterDetail();

  // マウント時に受診情報を取得する
  useEffect(() => {
    load(encounterId);
  }, [encounterId, load]);

  // --- 非 loaded 状態 ---

  if (status === "loading" || status === "idle") {
    return (
      <main className="mx-auto max-w-3xl px-4 py-8">
        <nav className="mb-6">
          <BackButton label="← 患者詳細に戻る" />
        </nav>
        <p className="text-center text-slate">読み込み中…</p>
      </main>
    );
  }

  if (status === "not_found") {
    return (
      <main className="mx-auto max-w-3xl px-4 py-8">
        <nav className="mb-6">
          <BackButton label="← 患者詳細に戻る" />
        </nav>
        <p className="text-center text-slate">受診が見つかりません</p>
      </main>
    );
  }

  if (status === "error" || encounter === null) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-8">
        <nav className="mb-6">
          <BackButton label="← 患者詳細に戻る" />
        </nav>
        <p className="text-center text-error" role="alert">
          受診情報の取得に失敗しました
        </p>
      </main>
    );
  }

  // --- loaded 状態 ---

  // clinician_id は最初の 8 hex 文字 + 省略記号で表示する
  const shortClinicianId = `${encounter.clinician_id.replace(/-/g, "").slice(0, 8)}…`;

  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <nav className="mb-6">
        <BackButton label="← 患者詳細に戻る" />
      </nav>

      {/* 受診カード */}
      <section
        aria-label="受診情報"
        className="mb-8 rounded-[8px] border border-slate/20 bg-surface p-6 shadow-sm"
      >
        <h1 className="mb-4 font-display text-2xl font-bold text-navy">受診詳細</h1>
        <dl className="space-y-2">
          <div className="flex gap-4">
            <dt className="w-32 text-sm font-medium text-slate">受診日</dt>
            <dd className="text-sm text-navy">{formatJpDate(encounter.encountered_at)}</dd>
          </div>
          <div className="flex gap-4">
            <dt className="w-32 text-sm font-medium text-slate">担当医 ID</dt>
            <dd className="font-mono text-sm text-navy">{shortClinicianId}</dd>
          </div>
          <div className="flex gap-4">
            <dt className="w-32 text-sm font-medium text-slate">登録日時</dt>
            <dd className="text-sm text-navy">{formatJpDateTime(encounter.created_at)}</dd>
          </div>
        </dl>
      </section>

      {/* 下書きを作成 / 編集 ボタン */}
      <div className="mb-8">
        <Link
          href={`/encounters/${encounterId}/draft`}
          className="inline-block rounded-[8px] bg-navy px-5 py-2.5 text-sm font-medium text-white hover:bg-[#020617]"
        >
          下書きを作成 / 編集
        </Link>
      </div>

      {/* 下書き一覧 */}
      <section aria-label="下書き一覧" className="mb-8">
        <h2 className="mb-4 font-display text-xl font-semibold text-navy">下書き</h2>

        {drafts.length === 0 ? (
          <p className="text-sm text-slate">下書きがありません</p>
        ) : (
          <ul className="space-y-2">
            {drafts.map((draft) => (
              <li
                key={draft.id}
                className="rounded-[8px] border border-slate/20 bg-surface px-4 py-3"
              >
                <p className="mb-1 text-xs text-slate">{formatJpDateTime(draft.created_at)}</p>
                <p className="text-sm text-navy">
                  {draft.content.length > 80 ? `${draft.content.slice(0, 80)}…` : draft.content}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* 確定カルテ一覧 */}
      <section aria-label="確定カルテ一覧" className="mb-8">
        <h2 className="mb-4 font-display text-xl font-semibold text-navy">確定カルテ</h2>

        {finals.length === 0 ? (
          <p className="text-sm text-slate">確定カルテがありません</p>
        ) : (
          <ul className="space-y-2">
            {finals.map((final) => (
              <li
                key={final.id}
                className="rounded-[8px] border border-slate/20 bg-surface px-4 py-3"
              >
                <p className="mb-1 text-xs text-slate">{formatJpDateTime(final.created_at)}</p>
                <p className="text-sm text-navy">
                  {final.content.length > 80 ? `${final.content.slice(0, 80)}…` : final.content}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
