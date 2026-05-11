/**
 * カルテ下書き生成フック。
 *
 * - AbortController: cancel() で進行中リクエストをキャンセルする。
 * - elapsedMs: ~100ms 間隔で更新し、ページ側がレイテンシ UX 階層を決定するために使う。
 * - PHI (clinicalInput, draft, streamingText) はこのフック内でログに出力しない。
 * - 状態は React state のみに保持し、localStorage / sessionStorage / URL には書き込まない。
 *
 * FE-008: generateStream() を追加。SSE ストリーミングパスで下書きを生成する。
 * 既存の generate() は後方互換のため保持する。
 */
"use client";

import { useState, useRef, useCallback } from "react";
import { createRecordDraft, streamRecordDraft } from "@/services/drafts";
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
  /** 下書き生成を開始する — 非ストリーミング (後方互換) */
  generate: () => void;
  /**
   * ストリーミングで下書きを生成する (FE-008)。
   * SSE チャンクが届くたびに streamingText が更新される。
   * 完了時に status が "success" になり draft がセットされる。
   */
  generateStream: () => void;
  /**
   * ストリーミング受信中のテキスト蓄積バッファ (PHI)。
   * status === "generating" && isStreaming の間のみ意味を持つ。
   * ページ側が AIIndicatedText + Cursor の中に表示する。
   */
  streamingText: string;
  /**
   * ストリーミングが進行中かどうか。
   * status === "generating" かつ elapsedMs > 0 かつ generateStream() 経由のとき true。
   */
  isStreaming: boolean;
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
  // FE-008: ストリーミングテキスト蓄積バッファ (PHI)
  const [streamingText, setStreamingText] = useState<string>("");
  // FE-008: generateStream() が進行中かどうか
  const [isStreaming, setIsStreaming] = useState<boolean>(false);

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
    setIsStreaming(false);
    setStreamingText("");
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
    setIsStreaming(false);
    setStreamingText("");

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

  // FE-008: SSE ストリーミングパスで下書きを生成する
  const generateStream = useCallback(() => {
    // 多重実行防止
    if (status === "generating") return;

    // 前のリクエストが残っていればキャンセル
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus("generating");
    setDraft(null);
    setError(null);
    setElapsedMs(0);
    setStreamingText("");
    setIsStreaming(true);

    // ~100ms 間隔で elapsed を更新する
    startTimeRef.current = Date.now();
    timerRef.current = setInterval(() => {
      setElapsedMs(Date.now() - startTimeRef.current);
    }, 100);

    const input = clinicalInput;

    void (async () => {
      try {
        await streamRecordDraft(encounterId, input, {
          signal: controller.signal,
          onChunk: (text) => {
            // PHI — ログ不可。蓄積バッファに追加する
            setStreamingText((prev) => prev + text);
          },
          onComplete: ({ draftId, confidence }) => {
            stopTimer();
            setElapsedMs(0);
            setIsStreaming(false);
            // 蓄積テキストから draft オブジェクトを組み立てる
            // content は setStreamingText で蓄積した値を直接 snapshot できないため
            // 関数形式の setState を使って最新値を取得する
            setStreamingText((accumulated) => {
              const assembledDraft: RecordDraft = {
                id: draftId,
                encounter_id: encounterId,
                content: accumulated,
                confidence,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              };
              setDraft(assembledDraft);
              setStatus("success");
              setError(null);
              // streamingText はそのまま保持 (成功後はページが Cursor を unmount する)
              return accumulated;
            });
          },
          onError: ({ kind }) => {
            stopTimer();
            setElapsedMs(0);
            setIsStreaming(false);
            setStreamingText("");
            switch (kind) {
              case "encounter_not_found":
                setStatus("encounter_not_found");
                setError(toErrorMessage("encounter_not_found"));
                break;
              case "inference_unavailable":
                setStatus("inference_unavailable");
                setError(toErrorMessage("inference_unavailable"));
                break;
              case "validation_error":
              case "error":
              default:
                setStatus("error");
                setError(toErrorMessage("error"));
                break;
            }
          },
        });
      } catch (err) {
        // AbortError はキャンセルの正常系 — cancel() が状態を処理済みなので何もしない
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        stopTimer();
        setElapsedMs(0);
        setIsStreaming(false);
        setStreamingText("");
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
    generateStream,
    streamingText,
    isStreaming,
    cancel,
    elapsedMs,
  };
}
