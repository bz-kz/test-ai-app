/**
 * useFinalChain — 確定カルテ訂正チェーン取得フック (FE-006)。
 *
 * finalized モードで currentFinal.id が変わるたびに呼ばれ、
 * predecessor チェーンを取得して ChainList コンポーネントに渡す。
 * - AbortController: load() の多重呼び出しで前のリクエストをキャンセルする。
 * - PHI (chain[].content) はこのフック内でログに出力しない。
 * - 状態は React state のみに保持し、localStorage / sessionStorage / URL には書き込まない。
 */
"use client";

import { useState, useRef, useCallback } from "react";
import { getFinalChain } from "@/services/finals";
import type { RecordFinal } from "@/types/recordFinal";

export type FinalChainStatus = "idle" | "loading" | "loaded" | "not_found" | "error";

export interface UseFinalChainReturn {
  /** 取得ステータス */
  status: FinalChainStatus;
  /** 訂正チェーン (oldest → newest) — デフォルト空配列 */
  chain: RecordFinal[];
  /** ユーザー向け日本語エラーメッセージ (PHI なし) */
  error: string | null;
  /**
   * チェーンを取得する。
   * 既に in-flight のリクエストがあれば AbortController でキャンセルしてから再発行する。
   */
  load: (finalId: string) => void;
}

export function useFinalChain(): UseFinalChainReturn {
  const [status, setStatus] = useState<FinalChainStatus>("idle");
  const [chain, setChain] = useState<RecordFinal[]>([]);
  const [error, setError] = useState<string | null>(null);

  // 進行中リクエストを管理する AbortController — 多重呼び出し時に前のリクエストをキャンセルする
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback((finalId: string) => {
    // 前のリクエストが残っていればキャンセル
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus("loading");
    setChain([]);
    setError(null);

    void (async () => {
      try {
        const result = await getFinalChain(finalId, { signal: controller.signal });

        switch (result.kind) {
          case "found":
            // バックエンドが oldest → newest 順で返す (BE-008 契約)
            setChain(result.chain);
            setStatus("loaded");
            setError(null);
            break;

          case "not_found":
            setStatus("not_found");
            setError("確定カルテが見つかりません。");
            break;

          case "error":
            setStatus("error");
            setError("訂正履歴の読み込み中にエラーが発生しました。");
            break;
        }
      } catch (err) {
        // AbortError はキャンセルの正常系 — 状態を変更しない
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        setStatus("error");
        setError("訂正履歴の読み込み中にエラーが発生しました。");
      }
    })();
  }, []);

  return {
    status,
    chain,
    error,
    load,
  };
}
