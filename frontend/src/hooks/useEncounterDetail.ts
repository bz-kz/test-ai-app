/**
 * useEncounterDetail — 受診詳細 + 下書き一覧 + 確定カルテ一覧取得フック (FE-007)。
 *
 * - Promise.all で受診情報・下書き一覧・確定カルテ一覧を並列取得する。
 * - AbortController: load() の多重呼び出しで前のリクエストをキャンセルする。
 * - PHI (drafts[].content, finals[].content) はこのフック内でログに出力しない。
 * - 状態は React state のみに保持し、localStorage / sessionStorage / URL には書き込まない。
 *
 * ステータス遷移:
 *   idle → loading → loaded | not_found | error
 */
"use client";

import { useState, useRef, useCallback } from "react";
import { getEncounterById, listFinalsByEncounter } from "@/services/encounters";
import { listDraftsByEncounter } from "@/services/drafts";
import type { Encounter } from "@/types/encounter";
import type { RecordDraft } from "@/types/recordDraft";
import type { RecordFinal } from "@/types/recordFinal";

export type EncounterDetailStatus = "idle" | "loading" | "loaded" | "not_found" | "error";

export interface UseEncounterDetailReturn {
  /** 取得ステータス */
  status: EncounterDetailStatus;
  /** 受診情報 (loaded 時のみ非 null) */
  encounter: Encounter | null;
  /** 下書き一覧 — created_at DESC (loaded 時のみ有効) */
  drafts: RecordDraft[];
  /** 確定カルテ一覧 — created_at DESC (loaded 時のみ有効) */
  finals: RecordFinal[];
  /** ユーザー向け日本語エラーメッセージ (PHI なし) */
  error: string | null;
  /**
   * 受診詳細・下書き一覧・確定カルテ一覧を取得する。
   * 既に in-flight のリクエストがあれば AbortController でキャンセルしてから再発行する。
   */
  load: (encounterId: string) => void;
}

export function useEncounterDetail(): UseEncounterDetailReturn {
  const [status, setStatus] = useState<EncounterDetailStatus>("idle");
  const [encounter, setEncounter] = useState<Encounter | null>(null);
  const [drafts, setDrafts] = useState<RecordDraft[]>([]);
  const [finals, setFinals] = useState<RecordFinal[]>([]);
  const [error, setError] = useState<string | null>(null);

  // 進行中リクエストを管理する AbortController
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback((encounterId: string) => {
    // 前のリクエストが残っていればキャンセル
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus("loading");
    setEncounter(null);
    setDrafts([]);
    setFinals([]);
    setError(null);

    void (async () => {
      try {
        // 受診情報・下書き一覧・確定カルテ一覧を並列取得する
        const [encounterResult, draftsResult, finalsResult] = await Promise.all([
          getEncounterById(encounterId, { signal: controller.signal }),
          listDraftsByEncounter(encounterId, { signal: controller.signal }),
          listFinalsByEncounter(encounterId, { signal: controller.signal }),
        ]);

        // 受診が見つからない場合は not_found へ遷移
        if (encounterResult.kind === "not_found") {
          setStatus("not_found");
          setError(null);
          return;
        }

        if (encounterResult.kind === "error") {
          setStatus("error");
          setError("受診情報の取得に失敗しました。");
          return;
        }

        const draftList = draftsResult.kind === "found" ? draftsResult.drafts : [];
        const finalList = finalsResult.kind === "found" ? finalsResult.finals : [];

        setEncounter(encounterResult.encounter);
        setDrafts(draftList);
        setFinals(finalList);
        setStatus("loaded");
        setError(null);
      } catch (err) {
        // AbortError はキャンセルの正常系 — 状態を変更しない
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        setStatus("error");
        setError("受診情報の取得に失敗しました。");
      }
    })();
  }, []);

  return { status, encounter, drafts, finals, error, load };
}
