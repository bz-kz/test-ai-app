"use client";

/**
 * /encounters/[encounterId]/draft ページ — カルテ下書き生成・編集・確定・訂正。
 *
 * - useGenerateDraft: 生成フロー (FE-003)
 * - useDraftLifecycle: 編集・承認フロー (FE-004)
 * - useCorrectFinal: 確定カルテ訂正フロー (FE-005)
 * - useEncounterDrafts: ページマウント時に既存下書きを自動ロードする (FE-006)
 * - useFinalChain: finalized モードで訂正履歴チェーンを取得する (FE-006)
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
 *   lifecycle.mode === "finalized" && correction.mode === "view"
 *     → 確定済みバッジ + 確定カルテ本文 + 訂正ボタン + ChainList
 *   lifecycle.mode === "finalized" && correction.mode === "correcting"
 *     → TextArea (pre-fill) + キャンセル / 更新ボタン
 */

import React, { useState, useEffect, useCallback } from "react";
import { useGenerateDraft } from "@/hooks/useGenerateDraft";
import { useDraftLifecycle } from "@/hooks/useDraftLifecycle";
import { useCorrectFinal } from "@/hooks/useCorrectFinal";
import { useEncounterDrafts } from "@/hooks/useEncounterDrafts";
import { useEncounterFinals } from "@/hooks/useEncounterFinals";
import { useFinalChain } from "@/hooks/useFinalChain";
import { LATENCY_SPINNER_MS } from "@/lib/constants";
import Button from "@/components/atoms/Button";
import BackButton from "@/components/atoms/BackButton";
import TextArea from "@/components/atoms/TextArea";
import FormField from "@/components/molecules/FormField";
import VoiceCapture from "@/components/molecules/VoiceCapture";
import DraftGeneratingIndicator from "./_sections/DraftGeneratingIndicator";
import DraftViewSection from "./_sections/DraftViewSection";
import DraftEditingSection from "./_sections/DraftEditingSection";
import DraftFinalizedSection from "./_sections/DraftFinalizedSection";
import type { RecordFinal } from "@/types/recordFinal";

interface DraftPageProps {
  // Next.js 15 では params は Promise として提供される
  params: Promise<{ encounterId: string }>;
}

export default function DraftPage({ params }: DraftPageProps) {
  // Next.js 15 の async params を React.use() で同期的に読み取る
  const { encounterId } = React.use(params);

  // BE-012 以降: clinician_id は X-Clinician-Id ヘッダー経由で apiFetch に注入される (lib/api.ts + CLINICIAN_ID constant)

  const gen = useGenerateDraft(encounterId);
  const {
    clinicalInput,
    setClinicalInput,
    status,
    draft,
    setDraft,
    error,
    generateStream,
    streamingText,
    isStreaming,
    cancel,
    elapsedMs,
  } = gen;

  // FE-010: ページマウント時に既存の確定カルテを並行して取得する
  const encounterFinals = useEncounterFinals();

  useEffect(() => {
    encounterFinals.load(encounterId);
    // encounterId が変わったときのみ再実行する
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [encounterId]);

  // onDraftUpdated で saveEdit 成功時に draft を即座に更新する (FE-005 fix #2)
  // initialFinal: 既存の確定カルテがあればそれを初期値として渡す (FE-010)
  const lifecycle = useDraftLifecycle(draft, {
    onDraftUpdated: setDraft,
    initialFinal: encounterFinals.latest,
  });

  // currentFinal: lifecycle.approve() 成功後の確定カルテ、または訂正後の最新版
  const [currentFinal, setCurrentFinal] = useState<RecordFinal | null>(null);

  // lifecycle.final が設定されたとき (approve 成功) に currentFinal を初期化する
  useEffect(() => {
    if (lifecycle.final !== null) {
      setCurrentFinal(lifecycle.final);
    }
  }, [lifecycle.final]);

  const correction = useCorrectFinal(currentFinal);

  // 訂正成功後: correctedFinal を currentFinal として採用し chain head を更新する
  useEffect(() => {
    if (correction.correctedFinal !== null) {
      setCurrentFinal(correction.correctedFinal);
    }
  }, [correction.correctedFinal]);

  // FE-006: ページマウント時に既存の下書きを自動ロードする
  const encounterDrafts = useEncounterDrafts();

  useEffect(() => {
    encounterDrafts.load(encounterId);
    // encounterId が変わったときのみ再実行する (実際には SPA ルーティングで変わることはないが念のため)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [encounterId]);

  // FE-006: loaded かつ最新下書きが存在し、かつ現在 draft が null かつ確定カルテが存在しない場合に自動シードする
  // SPEC line 142: 確定カルテが存在する場合は auto-seed を抑制する
  useEffect(() => {
    if (
      encounterDrafts.status === "loaded" &&
      encounterDrafts.latest !== null &&
      draft === null &&
      encounterFinals.latest === null
    ) {
      setDraft(encounterDrafts.latest);
    }
  }, [encounterDrafts.status, encounterDrafts.latest, draft, setDraft, encounterFinals.latest]);

  // FE-006: finalized モードで currentFinal.id が変わるたびに訂正チェーンを取得する
  const finalChain = useFinalChain();

  useEffect(() => {
    if (lifecycle.mode === "finalized" && currentFinal !== null) {
      finalChain.load(currentFinal.id);
    }
    // currentFinal.id と lifecycle.mode の変化を監視する
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lifecycle.mode, currentFinal?.id]);

  // 音声文字起こし結果を clinicalInput に追記する (PHI — ログに出力しない)
  // setClinicalInput は (next: string) => void のため関数型アップデートは使えない。
  // clinicalInput を依存に含めて最新値を参照する。
  const appendTranscript = useCallback(
    (text: string) => {
      setClinicalInput(clinicalInput.length === 0 ? text : `${clinicalInput}\n${text}`);
    },
    [clinicalInput, setClinicalInput]
  );

  const isGenerating = status === "generating";
  const isButtonDisabled = clinicalInput.trim() === "" || isGenerating;
  // ≤300ms はボタン内スピナーを出さない (invisible tier)
  const showButtonSpinner = isGenerating && elapsedMs >= LATENCY_SPINNER_MS;

  // SPEC line 141: drafts または finals のどちらかが loading 中はローディング状態とみなす
  const isInitialLoading =
    encounterDrafts.status === "loading" || encounterFinals.status === "loading";

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <nav className="mb-6">
        <BackButton label="← 受診詳細に戻る" />
      </nav>
      <h1 className="mb-6 font-display text-2xl font-bold text-navy">カルテ下書き生成</h1>

      {/* 確定済みモードおよびローディング中は入力フォームを隠す */}
      {lifecycle.mode !== "finalized" && !isInitialLoading && (
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
          {/* 音声入力 — 編集中 / 生成中 / ストリーミング中は無効化する
              (確定済みモードではこのブロック自体が非表示になるため除外済み) */}
          <div className="mt-3">
            <VoiceCapture
              encounterId={encounterId}
              onTranscript={appendTranscript}
              disabled={lifecycle.mode === "editing" || isStreaming || isGenerating}
            />
          </div>
        </section>
      )}

      {/* 生成ボタン: 確定済みモード・編集モード・ローディング中は非表示 */}
      {lifecycle.mode !== "finalized" && lifecycle.mode !== "editing" && !isInitialLoading && (
        <div className="mb-8">
          <Button
            variant="primary"
            size="md"
            disabled={isButtonDisabled}
            loading={showButtonSpinner}
            onClick={generateStream}
          >
            下書きを生成
          </Button>
        </div>
      )}

      {/* 出力エリア */}
      <section aria-live="polite" aria-atomic="true">
        {/* ローディング中はインジケーターを表示し、他の UI をすべて抑制する */}
        {isInitialLoading && <p className="text-center text-slate">下書きを確認しています…</p>}

        {/* idle かつ下書きなし かつローディング完了: 案内テキスト */}
        {!isInitialLoading && status === "idle" && draft === null && (
          <>
            {lifecycle.mode !== "finalized" && (
              <p className="text-center text-slate">
                臨床入力を記入して『下書きを生成』を押してください
              </p>
            )}
          </>
        )}

        {/* generating: レイテンシ UX 階層 */}
        {!isInitialLoading && isGenerating && (
          <DraftGeneratingIndicator
            isStreaming={isStreaming}
            streamingText={streamingText}
            elapsedMs={elapsedMs}
            onCancel={cancel}
          />
        )}

        {/* success + view モード: AI 下書き表示 + アクションボタン */}
        {!isInitialLoading &&
          status === "success" &&
          draft !== null &&
          lifecycle.mode === "view" && (
            <DraftViewSection draft={draft} lifecycle={lifecycle} onRegenerate={generateStream} />
          )}

        {/* success + editing モード: テキストエリア編集 */}
        {!isInitialLoading &&
          status === "success" &&
          draft !== null &&
          lifecycle.mode === "editing" && <DraftEditingSection lifecycle={lifecycle} />}

        {/* finalized モード: 確定済み表示 + 訂正フロー */}
        {!isInitialLoading && lifecycle.mode === "finalized" && currentFinal !== null && (
          <DraftFinalizedSection
            currentFinal={currentFinal}
            correction={correction}
            finalChain={finalChain}
          />
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
