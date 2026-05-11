/**
 * useEncounterDrafts — エンカウンター下書き一覧取得フック (FE-006)。
 *
 * ページマウント時に一度呼ばれ、既存の下書きを取得して自動再開を可能にする。
 * - AbortController: load() の多重呼び出しで前のリクエストをキャンセルする。
 * - PHI (drafts[].content) はこのフック内でログに出力しない。
 * - 状態は React state のみに保持し、localStorage / sessionStorage / URL には書き込まない。
 */
"use client";

import { useState, useRef, useCallback } from "react";
import { listDraftsByEncounter } from "@/services/drafts";
import type { RecordDraft } from "@/types/recordDraft";

export type EncounterDraftsStatus = "idle" | "loading" | "loaded" | "error";

export interface UseEncounterDraftsReturn {
  /** 取得ステータス */
  status: EncounterDraftsStatus;
  /** created_at DESC 順の下書き一覧 (loaded 時のみ有効) */
  drafts: RecordDraft[];
  /** 一覧の先頭 (最新) の下書き — 存在しない場合は null */
  latest: RecordDraft | null;
  /** ユーザー向け日本語エラーメッセージ (PHI なし) */
  error: string | null;
  /**
   * 下書き一覧を取得する。
   * 既に in-flight のリクエストがあれば AbortController でキャンセルしてから再発行する。
   */
  load: (encounterId: string) => void;
}

export function useEncounterDrafts(): UseEncounterDraftsReturn {
  const [status, setStatus] = useState<EncounterDraftsStatus>("idle");
  const [drafts, setDrafts] = useState<RecordDraft[]>([]);
  const [error, setError] = useState<string | null>(null);

  // 進行中リクエストを管理する AbortController — 多重呼び出し時に前のリクエストをキャンセルする
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback((encounterId: string) => {
    // 前のリクエストが残っていればキャンセル
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus("loading");
    setDrafts([]);
    setError(null);

    void (async () => {
      try {
        const result = await listDraftsByEncounter(encounterId, { signal: controller.signal });

        switch (result.kind) {
          case "found":
            setDrafts(result.drafts);
            setStatus("loaded");
            setError(null);
            break;

          case "error":
            setStatus("error");
            setError("下書きの確認中にエラーが発生しました。");
            break;
        }
      } catch (err) {
        // AbortError はキャンセルの正常系 — 状態を変更しない
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        setStatus("error");
        setError("下書きの確認中にエラーが発生しました。");
      }
    })();
  }, []);

  return {
    status,
    drafts,
    latest: drafts.length > 0 ? (drafts[0] ?? null) : null,
    error,
    load,
  };
}
