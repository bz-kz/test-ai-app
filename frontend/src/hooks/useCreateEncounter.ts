/**
 * useCreateEncounter — 新規受診作成フック (FE-007b)。
 *
 * ステータス遷移:
 *   idle → submitting → success → idle (reset() でクリア)
 *
 * - AbortController: submit() の多重呼び出しで前のリクエストをキャンセルする。
 * - PHI (patient_id, encountered_at) はこのフック内でログに出力しない。
 * - 状態は React state のみに保持し、localStorage / sessionStorage / URL には書き込まない。
 * - clinician_id は X-Clinician-Id ヘッダー経由で apiFetch が注入する (BE-012)。
 */
"use client";

import { useState, useRef, useCallback } from "react";
import { createEncounter } from "@/services/encounters";
import type { Encounter } from "@/types/encounter";

export type CreateEncounterStatus = "idle" | "submitting" | "success" | "error";

export interface UseCreateEncounterReturn {
  /** 送信ステータス */
  status: CreateEncounterStatus;
  /** 作成された受診 (success 時のみ非 null) */
  lastCreated: Encounter | null;
  /** ユーザー向け日本語エラーメッセージ (PHI なし) */
  error: string | null;
  /**
   * 新規受診を作成する。
   * 既に in-flight のリクエストがあれば AbortController でキャンセルしてから再発行する。
   *
   * @param patientId     患者 UUID
   * @param encounteredAt 受診日時 (ISO 8601 形式の文字列)
   */
  submit: (patientId: string, encounteredAt: string) => void;
  /**
   * 状態を idle にリセットし lastCreated をクリアする。
   * 送信成功後の UI リセットに使う。
   */
  reset: () => void;
}

export function useCreateEncounter(): UseCreateEncounterReturn {
  const [status, setStatus] = useState<CreateEncounterStatus>("idle");
  const [lastCreated, setLastCreated] = useState<Encounter | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 進行中リクエストを管理する AbortController
  const abortRef = useRef<AbortController | null>(null);

  const submit = useCallback((patientId: string, encounteredAt: string) => {
    // 前のリクエストが残っていればキャンセル
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus("submitting");
    setLastCreated(null);
    setError(null);

    void (async () => {
      try {
        const result = await createEncounter(
          { patient_id: patientId, encountered_at: encounteredAt },
          { signal: controller.signal }
        );

        switch (result.kind) {
          case "created":
            setLastCreated(result.encounter);
            setStatus("success");
            break;

          case "patient_not_found":
            setStatus("error");
            setError("患者が見つかりません。");
            break;

          case "validation_error":
            setStatus("error");
            setError("入力内容に誤りがあります。受診日を確認してください。");
            break;

          case "error":
            setStatus("error");
            setError("受診の作成に失敗しました。時間をおいて再試行してください。");
            break;
        }
      } catch (err) {
        // AbortError はキャンセルの正常系 — 状態を変更しない
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        setStatus("error");
        setError("受診の作成に失敗しました。時間をおいて再試行してください。");
      }
    })();
  }, []);

  const reset = useCallback(() => {
    setStatus("idle");
    setLastCreated(null);
    setError(null);
  }, []);

  return { status, lastCreated, error, submit, reset };
}
