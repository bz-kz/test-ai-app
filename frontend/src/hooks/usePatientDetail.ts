/**
 * usePatientDetail — 患者詳細 + 受診一覧取得フック (FE-007)。
 *
 * - Promise.all で患者情報と受診一覧を並列取得する。
 * - AbortController: load() の多重呼び出しで前のリクエストをキャンセルする。
 * - PHI (patient フィールド) はこのフック内でログに出力しない。
 * - 状態は React state のみに保持し、localStorage / sessionStorage / URL には書き込まない。
 *
 * ステータス遷移:
 *   idle → loading → loaded | not_found | error
 */
"use client";

import { useState, useRef, useCallback } from "react";
import { getPatientById } from "@/services/patients";
import { listEncountersByPatient } from "@/services/encounters";
import type { Patient } from "@/types/patient";
import type { Encounter } from "@/types/encounter";

export type PatientDetailStatus = "idle" | "loading" | "loaded" | "not_found" | "error";

export interface UsePatientDetailReturn {
  /** 取得ステータス */
  status: PatientDetailStatus;
  /** 患者情報 (loaded 時のみ非 null) — PHI */
  patient: Patient | null;
  /** 受診一覧 — newest-first (encountered_at DESC) (loaded 時のみ有効) */
  encounters: Encounter[];
  /** ユーザー向け日本語エラーメッセージ (PHI なし) */
  error: string | null;
  /**
   * 患者詳細と受診一覧を取得する。
   * 既に in-flight のリクエストがあれば AbortController でキャンセルしてから再発行する。
   */
  load: (patientId: string) => void;
}

export function usePatientDetail(): UsePatientDetailReturn {
  const [status, setStatus] = useState<PatientDetailStatus>("idle");
  const [patient, setPatient] = useState<Patient | null>(null);
  const [encounters, setEncounters] = useState<Encounter[]>([]);
  const [error, setError] = useState<string | null>(null);

  // 進行中リクエストを管理する AbortController
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback((patientId: string) => {
    // 前のリクエストが残っていればキャンセル
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus("loading");
    setPatient(null);
    setEncounters([]);
    setError(null);

    void (async () => {
      try {
        // 患者情報と受診一覧を並列取得する
        const [patientResult, encountersResult] = await Promise.all([
          getPatientById(patientId, { signal: controller.signal }),
          listEncountersByPatient(patientId, { signal: controller.signal }),
        ]);

        // 患者が見つからない場合は not_found へ遷移
        if (patientResult.kind === "not_found") {
          setStatus("not_found");
          setError(null);
          return;
        }

        if (patientResult.kind === "error") {
          setStatus("error");
          setError("患者情報の取得に失敗しました。");
          return;
        }

        // 受診一覧エラーは非致命的エラーとして扱う
        const encounterList = encountersResult.kind === "found" ? encountersResult.encounters : [];

        // newest-first (encountered_at DESC) でソートする
        const sorted = [...encounterList].sort(
          (a, b) => new Date(b.encountered_at).getTime() - new Date(a.encountered_at).getTime()
        );

        setPatient(patientResult.patient);
        setEncounters(sorted);
        setStatus("loaded");
        setError(null);
      } catch (err) {
        // AbortError はキャンセルの正常系 — 状態を変更しない
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        setStatus("error");
        setError("患者情報の取得に失敗しました。");
      }
    })();
  }, []);

  return { status, patient, encounters, error, load };
}
