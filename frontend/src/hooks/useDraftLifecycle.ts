/**
 * useDraftLifecycle — 下書き編集・確定フック。
 *
 * 生成済み下書きに対する「編集」と「承認 (確定カルテ昇格)」フローを管理する。
 * - AbortController: 進行中リクエストを再クリック時にキャンセルする。
 * - PHI (editContent, draft.content, final.content) はこのフック内でログに出力しない。
 * - 状態は React state のみに保持し、localStorage / sessionStorage / URL には書き込まない。
 *
 * 引数:
 *   draft           — useGenerateDraft が提供する現在の下書き (null のときは操作不可)
 *   clinicianId は不要 — BE-012 以降は X-Clinician-Id ヘッダー経由で認証する
 *   onDraftUpdated  — saveEdit 成功時に呼ばれるコールバック。
 *                     呼び出し元 (ページ) がこれを gen.setDraft に繋ぐことで、
 *                     ページリフレッシュなしに AIIndicatedText が最新内容を表示できる。
 *                     Option (b) を選択した理由: フックが戻り値で draft を返すより、
 *                     コールバックで「変更があったときだけ通知」する方が依存方向が
 *                     一方向に保たれ、テストでの検証も簡潔になる。
 *
 * 戻り値は UseDraftLifecycleReturn 参照。
 */
"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { editRecordDraft, finalizeRecordDraft } from "@/services/drafts";
import type { RecordDraft } from "@/types/recordDraft";
import type { RecordFinal } from "@/types/recordFinal";

export type DraftLifecycleMode = "view" | "editing" | "finalized";
export type DraftLifecycleStatus = "idle" | "saving" | "finalizing" | "error";

export interface UseDraftLifecycleOptions {
  /** saveEdit 成功時に呼ばれるコールバック。更新後の RecordDraft を受け取る。 */
  onDraftUpdated?: (next: RecordDraft) => void;
  /**
   * ページマウント時に既存の確定カルテが存在する場合に渡す初期値。
   * 非 null のとき、初回レンダーで mode を "finalized" に、final をその値に初期化する。
   * ラッチ: 一度初期化したあとは initialFinal が変化しても再シードしない。
   * これにより、他タブでの訂正でページが再レンダーされても mode が上書きされない。
   */
  initialFinal?: RecordFinal | null;
}

export interface UseDraftLifecycleReturn {
  /** 現在のモード */
  mode: DraftLifecycleMode;
  /** 編集中のテキストエリア制御値 (PHI) */
  editContent: string;
  setEditContent: (next: string) => void;
  /** view → editing に遷移し、editContent を現在の draft.content で初期化する */
  enterEditMode: () => void;
  /** editing → view に戻し、変更を破棄する */
  cancelEdit: () => void;
  /** PATCH を呼び出して下書きを更新し、成功時に view に戻る */
  saveEdit: () => Promise<void>;
  /** POST /finalize を呼び出して下書きを確定カルテに昇格させ、finalized に遷移する */
  approve: () => Promise<void>;
  /** 確定成功後の RecordFinal */
  final: RecordFinal | null;
  /** 操作中のステータス */
  status: DraftLifecycleStatus;
  /** ユーザー向け日本語エラーメッセージ (PHI なし) */
  error: string | null;
}

/**
 * サービスのエラータグをユーザー向け日本語メッセージに変換する。
 * PHI を含まない固定文言のみ使用する。
 */
function toErrorMessage(kind: string): string {
  switch (kind) {
    case "draft_not_found":
      return "下書きが見つかりません。ページを再読み込みしてください。";
    case "encounter_already_finalized":
      return "この受診には既に確定カルテが存在します。";
    case "validation_error":
      return "入力内容に問題があります。確認してください。";
    default:
      return "エラーが発生しました。もう一度お試しください。";
  }
}

/**
 * useDraftLifecycle フック。
 *
 * @param draft        現在の下書き (useGenerateDraft から渡す; null のときは操作不可)
 * @param opts         オプション (onDraftUpdated, initialFinal など)
 */
export function useDraftLifecycle(
  draft: RecordDraft | null,
  opts?: UseDraftLifecycleOptions
): UseDraftLifecycleReturn {
  const [mode, setMode] = useState<DraftLifecycleMode>("view");
  const [editContent, setEditContent] = useState<string>("");
  const [final, setFinal] = useState<RecordFinal | null>(null);
  const [status, setStatus] = useState<DraftLifecycleStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  // ラッチ: initialFinal による一度きりのシードを保証する。
  // ページマウント後に encounterFinals フェッチが完了すると initialFinal が
  // null → RecordFinal に変化する。この遷移を一度だけ捉えて mode と final を
  // 設定し、以降の変化 (他タブでの訂正など) では再シードしない。
  const seededRef = useRef<boolean>(false);

  useEffect(() => {
    // 既にシード済み、または initialFinal がまだ null なら何もしない
    if (seededRef.current || opts?.initialFinal == null) return;
    seededRef.current = true;
    setMode("finalized");
    setFinal(opts.initialFinal);
  }, [opts?.initialFinal]); // eslint-disable-line react-hooks/exhaustive-deps

  // 進行中リクエストを管理する AbortController — 再クリック時に前のリクエストをキャンセルする
  const abortRef = useRef<AbortController | null>(null);

  const enterEditMode = useCallback(() => {
    if (draft === null) return;
    setEditContent(draft.content);
    setMode("editing");
    setError(null);
  }, [draft]);

  const cancelEdit = useCallback(() => {
    // 進行中の save をキャンセルする
    abortRef.current?.abort();
    abortRef.current = null;
    setMode("view");
    setEditContent("");
    setStatus("idle");
    setError(null);
  }, []);

  const saveEdit = useCallback(async () => {
    if (draft === null) return;
    if (editContent.trim() === "") return;

    // 前のリクエストをキャンセルして新しいコントローラを発行する
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus("saving");
    setError(null);

    try {
      const result = await editRecordDraft(draft.id, editContent, {
        signal: controller.signal,
      });

      switch (result.kind) {
        case "updated":
          // 成功: view モードに戻り、onDraftUpdated コールバックで更新後の下書きを親に通知する。
          // ページは gen.setDraft をコールバックとして渡し、AIIndicatedText を即座に更新する。
          setMode("view");
          setEditContent("");
          setStatus("idle");
          setError(null);
          opts?.onDraftUpdated?.(result.draft);
          break;

        case "draft_not_found":
          setStatus("error");
          setError(toErrorMessage("draft_not_found"));
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
  }, [draft, editContent, opts]);

  const approve = useCallback(async () => {
    if (draft === null) return;

    // 前のリクエストをキャンセルして新しいコントローラを発行する
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus("finalizing");
    setError(null);

    try {
      const result = await finalizeRecordDraft(draft.id, {
        signal: controller.signal,
      });

      switch (result.kind) {
        case "finalized":
          setFinal(result.final);
          setMode("finalized");
          setStatus("idle");
          setError(null);
          break;

        case "draft_not_found":
          setStatus("error");
          setError(toErrorMessage("draft_not_found"));
          break;

        case "encounter_already_finalized":
          setStatus("error");
          setError(toErrorMessage("encounter_already_finalized"));
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
  }, [draft]);

  return {
    mode,
    editContent,
    setEditContent,
    enterEditMode,
    cancelEdit,
    saveEdit,
    approve,
    final,
    status,
    error,
  };
}
