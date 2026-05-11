/**
 * useCorrectFinal — 確定カルテ訂正フック。
 *
 * 確定カルテに対する「訂正」フロー (BE-008 POST /finals/{id}/correct) を管理する。
 * - mode "view": 確定カルテ表示 + 訂正ボタンを表示する状態。
 * - mode "correcting": TextArea に現在の content が pre-fill され、更新 / キャンセルボタンを表示する状態。
 *
 * AbortController: in-flight リクエストのキャンセルに使用する。
 * PHI (content): このフック内でログに出力しない。
 * 状態は React state のみに保持し、localStorage / sessionStorage / URL には書き込まない。
 *
 * 引数:
 *   sourceFinal   — 訂正元の確定カルテ (null のときは訂正不可)
 *   clinicianId   — 臨床医 UUID
 *
 * 戻り値は UseCorrectFinalReturn 参照。
 */
"use client";

import { useState, useRef, useCallback } from "react";
import { correctRecordFinal } from "@/services/finals";
import type { RecordFinal } from "@/types/recordFinal";

export type CorrectFinalMode = "view" | "correcting";
export type CorrectFinalStatus = "idle" | "submitting" | "error";

export interface UseCorrectFinalReturn {
  /** 現在のモード */
  mode: CorrectFinalMode;
  /** TextArea のコントロール値 (PHI) */
  content: string;
  setContent: (next: string) => void;
  /** view → correcting に遷移し、content を sourceFinal.content で初期化する */
  enter: () => void;
  /** correcting → view に戻し、変更を破棄する */
  cancel: () => void;
  /** POST を呼び出して訂正版を作成し、成功時に view に戻る */
  submit: () => Promise<void>;
  /** 操作中のステータス */
  status: CorrectFinalStatus;
  /** ユーザー向け日本語エラーメッセージ (PHI なし) */
  error: string | null;
  /**
   * 訂正成功後の新しい確定カルテ。
   * ページはこれを currentFinal として使い、新しい chain head として表示する。
   */
  correctedFinal: RecordFinal | null;
}

/**
 * エラータグをユーザー向け日本語メッセージに変換する。
 * PHI を含まない固定文言のみ使用する。
 */
function toErrorMessage(kind: string): string {
  switch (kind) {
    case "final_not_found":
      return "確定カルテが見つかりません。ページを再読み込みしてください。";
    case "validation_error":
      return "入力内容に問題があります。確認してください。";
    default:
      return "エラーが発生しました。もう一度お試しください。";
  }
}

/**
 * useCorrectFinal フック。
 *
 * @param sourceFinal  訂正元の確定カルテ (null のときは訂正不可)
 * @param clinicianId  臨床医 UUID
 */
export function useCorrectFinal(
  sourceFinal: RecordFinal | null,
  clinicianId: string
): UseCorrectFinalReturn {
  const [mode, setMode] = useState<CorrectFinalMode>("view");
  const [content, setContent] = useState<string>("");
  const [correctedFinal, setCorrectedFinal] = useState<RecordFinal | null>(null);
  const [status, setStatus] = useState<CorrectFinalStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  // 進行中リクエストを管理する AbortController
  const abortRef = useRef<AbortController | null>(null);

  const enter = useCallback(() => {
    if (sourceFinal === null) return;
    setContent(sourceFinal.content);
    setMode("correcting");
    setError(null);
  }, [sourceFinal]);

  const cancel = useCallback(() => {
    // in-flight リクエストをキャンセルする
    abortRef.current?.abort();
    abortRef.current = null;
    setMode("view");
    setContent("");
    setStatus("idle");
    setError(null);
  }, []);

  const submit = useCallback(async () => {
    if (sourceFinal === null) return;
    if (content.trim() === "") return;

    // 前のリクエストをキャンセルして新しいコントローラを発行する
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus("submitting");
    setError(null);

    try {
      const result = await correctRecordFinal(sourceFinal.id, content, clinicianId, {
        signal: controller.signal,
      });

      switch (result.kind) {
        case "created":
          // 成功: correctedFinal を設定して view に戻る
          setCorrectedFinal(result.final);
          setMode("view");
          setContent("");
          setStatus("idle");
          setError(null);
          break;

        case "final_not_found":
          setStatus("error");
          setError(toErrorMessage("final_not_found"));
          break;

        case "validation_error":
          setStatus("error");
          setError(toErrorMessage("validation_error"));
          break;

        case "error":
          setStatus("error");
          setError(toErrorMessage("error"));
          break;
      }
    } catch (err) {
      // AbortError はキャンセルの正常系 — モードを変更しない
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      setStatus("error");
      setError(toErrorMessage("error"));
    }
  }, [sourceFinal, content, clinicianId]);

  return {
    mode,
    content,
    setContent,
    enter,
    cancel,
    submit,
    status,
    error,
    correctedFinal,
  };
}
