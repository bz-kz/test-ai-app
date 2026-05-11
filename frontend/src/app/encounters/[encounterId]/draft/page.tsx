"use client";

/**
 * /encounters/[encounterId]/draft ページ — カルテ下書き生成。
 *
 * - useGenerateDraft フックを使い、臨床入力から AI 下書きを生成する。
 * - PHI (clinicalInput, draft.content) は console.* に出力しない。
 * - PHI は localStorage / sessionStorage / indexedDB / cookies に書き込まない。
 * - clinicalInput は URL / searchParams に含めない。
 * - fetch は直接呼び出さない (フック → サービス層に委譲)。
 *
 * レイテンシ UX 階層 (frontend/SPEC.md#latency-ux-budget):
 *   idle / elapsedMs < 300ms  : 空の出力エリア (何も表示しない)
 *   generating / elapsedMs < 1000ms : ボタン内スピナーのみ
 *   generating / 1000ms <= elapsedMs < 3000ms : スケルトン
 *   generating / 3000ms <= elapsedMs < 10000ms : スケルトン + ヒント
 *   generating / elapsedMs >= 10000ms : スケルトン + ヒント + キャンセルボタン
 *   success : AIIndicatedText で下書きを表示
 *   encounter_not_found / inference_unavailable / error : エラーメッセージ
 */

import React from "react";
import { useGenerateDraft } from "@/hooks/useGenerateDraft";
import {
  LATENCY_SPINNER_MS,
  LATENCY_SKELETON_MS,
  LATENCY_HINT_MS,
  LATENCY_CANCEL_MS,
} from "@/lib/constants";
import Button from "@/components/atoms/Button";
import TextArea from "@/components/atoms/TextArea";
import FormField from "@/components/molecules/FormField";
import AIIndicatedText from "@/components/molecules/AIIndicatedText";

interface DraftPageProps {
  // Next.js 15 では params は Promise として提供される
  params: Promise<{ encounterId: string }>;
}

export default function DraftPage({ params }: DraftPageProps) {
  // Next.js 15 の async params を React.use() で同期的に読み取る
  const { encounterId } = React.use(params);

  const { clinicalInput, setClinicalInput, status, draft, error, generate, cancel, elapsedMs } =
    useGenerateDraft(encounterId);

  const isGenerating = status === "generating";
  const isButtonDisabled = clinicalInput.trim() === "" || isGenerating;
  // ≤300ms はボタン内スピナーを出さない (invisible tier)
  const showButtonSpinner = isGenerating && elapsedMs >= LATENCY_SPINNER_MS;

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-6 font-display text-2xl font-bold text-navy">カルテ下書き生成</h1>

      <section className="mb-6">
        <FormField id="clinical-input" label="臨床入力 (Subjective/Objective)">
          <TextArea
            id="clinical-input"
            value={clinicalInput}
            onChange={(e) => setClinicalInput(e.target.value)}
            placeholder="主訴・現病歴・身体所見などを入力してください"
            disabled={isGenerating}
            rows={6}
            aria-describedby={undefined}
          />
        </FormField>
      </section>

      <div className="mb-8">
        <Button
          variant="primary"
          size="md"
          disabled={isButtonDisabled}
          loading={showButtonSpinner}
          onClick={generate}
        >
          下書きを生成
        </Button>
      </div>

      {/* 出力エリア */}
      <section aria-live="polite" aria-atomic="true">
        {/* idle かつ下書きなし: 案内テキスト */}
        {status === "idle" && draft === null && (
          <p className="text-center text-slate">
            臨床入力を記入して『下書きを生成』を押してください
          </p>
        )}

        {/* generating: レイテンシ UX 階層 */}
        {isGenerating && (
          <div>
            {/* 1000ms 未満: 空の出力エリア (スピナーはボタン内) — 何も表示しない */}

            {/* 1000ms 以上: スケルトン */}
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

            {/* 10000ms 以上: キャンセルボタン */}
            {elapsedMs >= LATENCY_CANCEL_MS && (
              <div className="mt-4">
                <Button variant="secondary" size="sm" onClick={cancel}>
                  キャンセル
                </Button>
              </div>
            )}
          </div>
        )}

        {/* success: AI 生成下書きを表示 */}
        {status === "success" && draft !== null && (
          <AIIndicatedText>
            {/* SOAP 形式の改行を段落として表示する。splitは改行区切りで段落を生成する */}
            <pre className="whitespace-pre-wrap font-body text-sm text-navy">{draft.content}</pre>
          </AIIndicatedText>
        )}

        {/* encounter_not_found */}
        {status === "encounter_not_found" && (
          <p className="text-center text-error" role="alert">
            {error ?? "Encounter が見つかりません。"}
          </p>
        )}

        {/* inference_unavailable */}
        {status === "inference_unavailable" && (
          <p className="text-center text-error" role="alert">
            {error ?? "推論サービスが一時的に利用できません。しばらく待って再試行してください。"}
          </p>
        )}

        {/* generic error */}
        {status === "error" && (
          <p className="text-center text-error" role="alert">
            {error ?? "下書きの生成に失敗しました。"}
          </p>
        )}
      </section>
    </main>
  );
}
