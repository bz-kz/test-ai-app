/**
 * カルテ下書き生成フック。
 *
 * - AbortController: cancel() で進行中リクエストをキャンセルする。
 * - elapsedMs: ~100ms 間隔で更新し、ページ側がレイテンシ UX 階層を決定するために使う。
 * - PHI (clinicalInput, draft) はこのフック内でログに出力しない。
 * - 状態は React state のみに保持し、localStorage / sessionStorage / URL には書き込まない。
 */
"use client";

import { useState, useRef, useCallback } from "react";
import { createRecordDraft } from "@/services/drafts";
import type { RecordDraft } from "@/types/recordDraft";

export type GenerateDraftStatus =
  | "idle"
  | "generating"
  | "success"
  | "encounter_not_found"
  | "inference_unavailable"
  | "error";

export interface UseGenerateDraftReturn {
  /** 臨床入力テキスト (PHI) — テキストエリアのコントロール値 */
  clinicalInput: string;
  setClinicalInput: (next: string) => void;
  /** 生成ステータス */
  status: GenerateDraftStatus;
  /** 生成成功時の下書き (PHI) */
  draft: RecordDraft | null;
  /**
   * 外部から下書きを直接置き換えるセッター。
   * useDraftLifecycle の onDraftUpdated コールバックから呼ばれ、
   * saveEdit 成功後に画面を再レンダリングする (ページリフレッシュ不要)。
   */
  setDraft: (next: RecordDraft | null) => void;
  /** ユーザー向け日本語エラーメッセージ (PHI なし) */
  error: string | null;
  /** 下書き生成を開始する (ユーザー起点のアクション、デバウンスなし) */
  generate: () => void;
  /** 進行中リクエストをキャンセルし、idle に戻す */
  cancel: () => void;
  /** generating 中の経過時間 (ms)。generating 以外では 0 */
  elapsedMs: number;
}

/**
 * ステータスに対応するユーザー向けエラーメッセージ。
 * PHI を含まない固定文言のみ使用する。
 */
function toErrorMessage(kind: string): string | null {
  switch (kind) {
    case "encounter_not_found":
      return "Encounter が見つかりません。";
    case "inference_unavailable":
      return "推論サービスが一時的に利用できません。しばらく待って再試行してください。";
    case "error":
      return "下書きの生成に失敗しました。";
    default:
      return null;
  }
}

export function useGenerateDraft(encounterId: string): UseGenerateDraftReturn {
  const [clinicalInput, setClinicalInput] = useState<string>("");
  const [status, setStatus] = useState<GenerateDraftStatus>("idle");
  const [draft, setDraft] = useState<RecordDraft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsedMs, setElapsedMs] = useState<number>(0);

  // AbortController と elapsed タイマーは ref で管理し再レンダリングを不要にする
  const abortRef = useRef<AbortController | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(0);

  /** elapsed タイマーを停止してリセットする */
  const stopTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    stopTimer();
    setElapsedMs(0);
    setStatus("idle");
  }, [stopTimer]);

  const generate = useCallback(() => {
    // 多重実行防止: 既に generating 中なら何もしない
    if (status === "generating") return;

    // 前のリクエストが残っていればキャンセル
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus("generating");
    setDraft(null);
    setError(null);
    setElapsedMs(0);

    // ~100ms 間隔で elapsed を更新する (レイテンシ UX 階層の判定に使う)
    startTimeRef.current = Date.now();
    timerRef.current = setInterval(() => {
      setElapsedMs(Date.now() - startTimeRef.current);
    }, 100);

    // clinicalInput をクロージャでキャプチャし、非同期処理を実行する
    const input = clinicalInput;

    void (async () => {
      try {
        const result = await createRecordDraft(encounterId, input, {
          signal: controller.signal,
        });

        stopTimer();
        setElapsedMs(0);

        switch (result.kind) {
          case "created":
            setDraft(result.draft);
            setStatus("success");
            setError(null);
            break;
          case "encounter_not_found":
            setStatus("encounter_not_found");
            setError(toErrorMessage("encounter_not_found"));
            break;
          case "inference_unavailable":
            setStatus("inference_unavailable");
            setError(toErrorMessage("inference_unavailable"));
            break;
          case "validation_error":
            setStatus("error");
            setError(toErrorMessage("error"));
            break;
          case "error":
            setStatus("error");
            setError(toErrorMessage("error"));
            break;
        }
      } catch (err) {
        // AbortError はキャンセルの正常系 — cancel() が状態を処理済みなので何もしない
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        stopTimer();
        setElapsedMs(0);
        setStatus("error");
        setError(toErrorMessage("error"));
      }
    })();
  }, [status, clinicalInput, encounterId, stopTimer]);

  return {
    clinicalInput,
    setClinicalInput,
    status,
    draft,
    setDraft,
    error,
    generate,
    cancel,
    elapsedMs,
  };
}
