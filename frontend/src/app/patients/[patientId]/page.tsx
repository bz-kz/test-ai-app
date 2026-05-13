"use client";

/**
 * /patients/[patientId] ページ — 患者詳細 + 受診一覧 + 新規受診作成フォーム (FE-007b)。
 *
 * - usePatientDetail で患者情報と受診一覧を取得する。
 * - useCreateEncounter で新規受診を作成する。
 * - PHI (patient フィールド, content) は console.* に出力しない。
 * - PHI は localStorage / sessionStorage / indexedDB / URL には書き込まない。
 * - fetch は直接呼び出さない (フック → サービス層に委譲)。
 */
import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePatientDetail } from "@/hooks/usePatientDetail";
import { useCreateEncounter } from "@/hooks/useCreateEncounter";
import Input from "@/components/atoms/Input";
import Button from "@/components/atoms/Button";
import BackButton from "@/components/atoms/BackButton";
import { formatJpDate, formatJpDateTime } from "@/lib/dateFormat";

type Params = { patientId: string };

export default function PatientDetailPage({ params }: { params: Promise<Params> }) {
  const { patientId } = React.use(params);

  const { status, patient, encounters, load } = usePatientDetail();
  const createEnc = useCreateEncounter();

  const [dateInput, setDateInput] = useState("");
  const [showConfirmation, setShowConfirmation] = useState(false);
  const confirmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // マウント時に患者情報と受診一覧を取得する
  useEffect(() => {
    load(patientId);
  }, [patientId, load]);

  // 受診作成成功後: 一覧を再取得し確認メッセージを表示する
  useEffect(() => {
    if (createEnc.status === "success") {
      setDateInput("");
      setShowConfirmation(true);
      load(patientId);
      createEnc.reset();

      // 2s 後に確認メッセージを非表示にする
      if (confirmTimerRef.current) {
        clearTimeout(confirmTimerRef.current);
      }
      confirmTimerRef.current = setTimeout(() => {
        setShowConfirmation(false);
      }, 2000);
    }
    // createEnc.reset は useCallback の安定した参照のため依存に含める
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [createEnc.status]);

  // コンポーネントのアンマウント時にタイマーをクリアする
  useEffect(() => {
    return () => {
      if (confirmTimerRef.current) {
        clearTimeout(confirmTimerRef.current);
      }
    };
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!dateInput) return;
    // 受診日 (date 型の値) を ISO 8601 形式に変換して送信する
    createEnc.submit(patientId, `${dateInput}T00:00:00`);
  };

  // --- 非 loaded 状態 ---

  if (status === "loading" || status === "idle") {
    return (
      <main className="mx-auto max-w-3xl px-4 py-8">
        <nav className="mb-6">
          <BackButton label="← 患者検索に戻る" />
        </nav>
        <p className="text-center text-slate">読み込み中…</p>
      </main>
    );
  }

  if (status === "not_found") {
    return (
      <main className="mx-auto max-w-3xl px-4 py-8">
        <nav className="mb-6">
          <BackButton label="← 患者検索に戻る" />
        </nav>
        <p className="text-center text-slate">患者が見つかりません</p>
      </main>
    );
  }

  if (status === "error" || patient === null) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-8">
        <nav className="mb-6">
          <BackButton label="← 患者検索に戻る" />
        </nav>
        <p className="text-center text-error" role="alert">
          患者情報の取得に失敗しました
        </p>
      </main>
    );
  }

  // --- loaded 状態 ---

  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <nav className="mb-6">
        <BackButton label="← 患者検索に戻る" />
      </nav>

      {/* 患者カード */}
      <section
        aria-label="患者情報"
        className="mb-8 rounded-[8px] border border-slate/20 bg-surface p-6 shadow-sm"
      >
        <h1 className="mb-4 font-display text-2xl font-bold text-navy">
          {patient.family_name} {patient.given_name}
        </h1>
        <dl className="space-y-2">
          <div className="flex gap-4">
            <dt className="w-32 text-sm font-medium text-slate">診察番号</dt>
            <dd className="font-mono text-sm text-navy">{patient.mrn}</dd>
          </div>
          <div className="flex gap-4">
            <dt className="w-32 text-sm font-medium text-slate">生年月日</dt>
            <dd className="text-sm text-navy">{patient.date_of_birth}</dd>
          </div>
          <div className="flex gap-4">
            <dt className="w-32 text-sm font-medium text-slate">登録日時</dt>
            <dd className="text-sm text-navy">{formatJpDateTime(patient.created_at)}</dd>
          </div>
        </dl>
      </section>

      {/* 受診一覧 */}
      <section aria-label="受診一覧" className="mb-8">
        <h2 className="mb-4 font-display text-xl font-semibold text-navy">受診一覧</h2>

        {encounters.length === 0 ? (
          <p className="text-sm text-slate">受診記録がありません</p>
        ) : (
          <ul className="space-y-2">
            {encounters.map((enc) => (
              <li key={enc.id}>
                <Link
                  href={`/encounters/${enc.id}`}
                  className="block rounded-[8px] border border-slate/20 bg-surface px-4 py-3 text-sm text-navy hover:border-navy hover:bg-slate/5"
                >
                  {formatJpDate(enc.encountered_at)}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* 新規受診作成フォーム */}
      <section aria-label="新規受診を追加" className="rounded-[8px] border border-slate/20 p-6">
        <h2 className="mb-4 font-display text-xl font-semibold text-navy">新規受診を追加</h2>

        <form onSubmit={handleSubmit} className="flex items-end gap-4">
          <div className="flex-1">
            <label htmlFor="encountered-at" className="mb-1 block text-sm font-medium text-slate">
              受診日
            </label>
            <Input
              id="encountered-at"
              type="date"
              value={dateInput}
              onChange={(e) => setDateInput(e.target.value)}
              disabled={createEnc.status === "submitting"}
              aria-required="true"
            />
          </div>
          <Button
            type="submit"
            variant="primary"
            size="md"
            disabled={createEnc.status === "submitting" || !dateInput}
            loading={createEnc.status === "submitting"}
          >
            {createEnc.status === "submitting" ? "送信中…" : "追加"}
          </Button>
        </form>

        {/* 送信成功メッセージ */}
        {showConfirmation && (
          <p className="mt-3 text-sm text-sage" role="status" aria-live="polite">
            ✓ 受診を追加しました
          </p>
        )}

        {/* エラーメッセージ */}
        {createEnc.status === "error" && createEnc.error !== null && (
          <p className="mt-3 text-sm text-error" role="alert">
            {createEnc.error}
          </p>
        )}
      </section>
    </main>
  );
}
