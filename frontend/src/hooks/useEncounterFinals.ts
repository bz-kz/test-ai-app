/**
 * useEncounterFinals — エンカウンター確定カルテ一覧取得フック (FE-010)。
 *
 * useEncounterDrafts と同一のシェイプを持ち、ページマウント時に既存の確定カルテを
 * 取得して自動ファイナライズ状態を可能にする。
 * - AbortController: load() の多重呼び出しで前のリクエストをキャンセルする。
 * - PHI (finals[].content) はこのフック内でログに出力しない。
 * - 状態は React state のみに保持し、localStorage / sessionStorage / URL には書き込まない。
 */
"use client";

import { useState, useRef, useCallback } from "react";
import { listFinalsByEncounter } from "@/services/finals";
import type { RecordFinal } from "@/types/recordFinal";

export type EncounterFinalsStatus = "idle" | "loading" | "loaded" | "error";

export interface UseEncounterFinalsReturn {
  /** 取得ステータス */
  status: EncounterFinalsStatus;
  /** created_at DESC 順の確定カルテ一覧 (loaded 時のみ有効) */
  finals: RecordFinal[];
  /** 一覧の先頭 (最新) の確定カルテ — 存在しない場合は null */
  latest: RecordFinal | null;
  /** ユーザー向け日本語エラーメッセージ (PHI なし) */
  error: string | null;
  /**
   * 確定カルテ一覧を取得する。
   * 既に in-flight のリクエストがあれば AbortController でキャンセルしてから再発行する。
   */
  load: (encounterId: string) => void;
}

export function useEncounterFinals(): UseEncounterFinalsReturn {
  const [status, setStatus] = useState<EncounterFinalsStatus>("idle");
  const [finals, setFinals] = useState<RecordFinal[]>([]);
  const [error, setError] = useState<string | null>(null);

  // 進行中リクエストを管理する AbortController — 多重呼び出し時に前のリクエストをキャンセルする
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback((encounterId: string) => {
    // 前のリクエストが残っていればキャンセル
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus("loading");
    setFinals([]);
    setError(null);

    void (async () => {
      try {
        const result = await listFinalsByEncounter(encounterId, { signal: controller.signal });

        switch (result.kind) {
          case "found":
            setFinals(result.finals);
            setStatus("loaded");
            setError(null);
            break;

          case "error":
            setStatus("error");
            setError("確定カルテの確認中にエラーが発生しました。");
            break;
        }
      } catch (err) {
        // AbortError はキャンセルの正常系 — 状態を変更しない
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        setStatus("error");
        setError("確定カルテの確認中にエラーが発生しました。");
      }
    })();
  }, []);

  return {
    status,
    finals,
    latest: finals.length > 0 ? (finals[0] ?? null) : null,
    error,
    load,
  };
}
