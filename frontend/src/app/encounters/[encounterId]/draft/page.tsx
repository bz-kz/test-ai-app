"use client";

/**
 * /encounters/[encounterId]/draft ページ — カルテ下書き生成・編集・確定。
 *
 * - useGenerateDraft: 生成フロー (FE-003)
 * - useDraftLifecycle: 編集・承認フロー (FE-004)
 * - PHI (clinicalInput, draft.content, final.content) は console.* に出力しない。
 * - PHI は localStorage / sessionStorage / indexedDB / cookies に書き込まない。
 * - PHI は URL / searchParams に含めない。
 * - fetch は直接呼び出さない (フック → サービス層に委譲)。
 *
 * 状態機械の概要:
 *   useGenerateDraft.status === "generating"
 *     → レイテンシ UX 階層 (invisible / spinner / skeleton / hint / cancel)
 *   useGenerateDraft.status === "success" && lifecycle.mode === "view"
 *     → AIIndicatedText + ConfidencePill + 3アクションボタン (再生成 / 編集 / 承認)
 *   useGenerateDraft.status === "success" && lifecycle.mode === "editing"
 *     → TextArea + キャンセル / 更新ボタン
 *   lifecycle.mode === "finalized"
 *     → 確定済みバッジ + 確定カルテ本文 (アクションボタンなし)
 */

import React, { useState } from "react";
import { useGenerateDraft } from "@/hooks/useGenerateDraft";
import { useDraftLifecycle } from "@/hooks/useDraftLifecycle";
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
import ConfidencePill from "@/components/molecules/ConfidencePill";

interface DraftPageProps {
  // Next.js 15 では params は Promise として提供される
  params: Promise<{ encounterId: string }>;
}

/** 再生成アイコン (リフレッシュ) — インライン SVG */
function RefreshIcon() {
  return (
    <svg
      width={14}
      height={14}
      viewBox="0 0 14 14"
      fill="none"
      aria-hidden="true"
      className="shrink-0"
    >
      <path
        d="M12.5 2.5A6 6 0 1 1 7 1"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path d="M7 1l2 2-2 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

/** 編集アイコン (鉛筆) — インライン SVG */
function PencilIcon() {
  return (
    <svg
      width={14}
      height={14}
      viewBox="0 0 14 14"
      fill="none"
      aria-hidden="true"
      className="shrink-0"
    >
      <path
        d="M9.5 2.5l2 2-7 7H2.5v-2l7-7z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** 承認アイコン (チェック) — インライン SVG */
function CheckIcon() {
  return (
    <svg
      width={14}
      height={14}
      viewBox="0 0 14 14"
      fill="none"
      aria-hidden="true"
      className="shrink-0"
    >
      <path
        d="M2 7l3.5 3.5L12 4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** 錠前アイコン (確定済みバッジ用) — インライン SVG */
function LockIcon() {
  return (
    <svg
      width={14}
      height={14}
      viewBox="0 0 14 14"
      fill="none"
      aria-hidden="true"
      className="shrink-0"
    >
      <rect x="2.5" y="6.5" width="9" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M4.5 6.5V4.5a2.5 2.5 0 0 1 5 0v2"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default function DraftPage({ params }: DraftPageProps) {
  // Next.js 15 の async params を React.use() で同期的に読み取る
  const { encounterId } = React.use(params);

  // 臨床医 ID プレースホルダー (認証 Block で置き換える)
  const [clinicianId] = useState<string>("00000000-0000-0000-0000-000000000001");

  const { clinicalInput, setClinicalInput, status, draft, error, generate, cancel, elapsedMs } =
    useGenerateDraft(encounterId);

  const lifecycle = useDraftLifecycle(draft, clinicianId);

  const isGenerating = status === "generating";
  const isButtonDisabled = clinicalInput.trim() === "" || isGenerating;
  // ≤300ms はボタン内スピナーを出さない (invisible tier)
  const showButtonSpinner = isGenerating && elapsedMs >= LATENCY_SPINNER_MS;

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-6 font-display text-2xl font-bold text-navy">カルテ下書き生成</h1>

      {/* 確定済みモードでは入力フォームを隠す */}
      {lifecycle.mode !== "finalized" && (
        <section className="mb-6">
          <FormField id="clinical-input" label="臨床入力 (Subjective/Objective)">
            <TextArea
              id="clinical-input"
              value={clinicalInput}
              onChange={(e) => setClinicalInput(e.target.value)}
              placeholder="主訴・現病歴・身体所見などを入力してください"
              disabled={isGenerating || lifecycle.mode === "editing"}
              rows={6}
              aria-describedby={undefined}
            />
          </FormField>
        </section>
      )}

      {/* 生成ボタン: 確定済みモードおよび編集モードでは非表示 */}
      {lifecycle.mode !== "finalized" && lifecycle.mode !== "editing" && (
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
      )}

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

        {/* success + view モード: AI 下書き表示 + アクションボタン */}
        {status === "success" && draft !== null && lifecycle.mode === "view" && (
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
              {/* 再生成 — FE-003 の generate() を再実行する */}
              <Button variant="secondary" size="sm" onClick={generate}>
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
        )}

        {/* success + editing モード: テキストエリア編集 */}
        {status === "success" && draft !== null && lifecycle.mode === "editing" && (
          <div>
            <FormField id="edit-content" label="下書き編集">
              <TextArea
                id="edit-content"
                value={lifecycle.editContent}
                onChange={(e) => lifecycle.setEditContent(e.target.value)}
                rows={8}
                disabled={lifecycle.status === "saving"}
              />
            </FormField>

            <div className="mt-4 flex items-center gap-3">
              {/* キャンセル */}
              <Button
                variant="ghost"
                size="sm"
                onClick={lifecycle.cancelEdit}
                disabled={lifecycle.status === "saving"}
              >
                キャンセル
              </Button>

              {/* 更新 — editContent が空白のみの場合は無効 */}
              <Button
                variant="primary"
                size="sm"
                loading={lifecycle.status === "saving"}
                disabled={lifecycle.status === "saving" || lifecycle.editContent.trim() === ""}
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
        )}

        {/* finalized モード: 確定済み表示 (アクションボタンなし) */}
        {lifecycle.mode === "finalized" && lifecycle.final !== null && (
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

            {/* 確定カルテ本文 — AIIndicatedText で "確定カルテ" ラベルを付ける */}
            <AIIndicatedText label="確定カルテ">
              <pre className="whitespace-pre-wrap font-body text-sm text-navy">
                {lifecycle.final.content}
              </pre>
            </AIIndicatedText>
          </div>
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
