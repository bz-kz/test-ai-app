/**
 * MRN 検索フック。
 *
 * - 200ms デバウンス: 入力が落ち着いてから検索を発火する。
 * - AbortController: クエリ変更時に前の検索リクエストをキャンセルする。
 * - PHI (query / result) はこのフック内でログに出力しない。
 */
"use client";

import { useState, useEffect } from "react";
import { searchPatientsByMrn } from "@/services/patients";
import type { Patient } from "@/types/patient";

export type MrnSearchStatus = "idle" | "searching" | "found" | "not_found" | "error";

export interface UseMrnSearchReturn {
  query: string;
  setQuery: (next: string) => void;
  status: MrnSearchStatus;
  result: Patient | null;
}

export function useMrnSearch(): UseMrnSearchReturn {
  const [query, setQuery] = useState<string>("");
  const [status, setStatus] = useState<MrnSearchStatus>("idle");
  const [result, setResult] = useState<Patient | null>(null);

  useEffect(() => {
    // 空クエリはアイドルに戻して何もしない
    if (query.trim() === "") {
      setStatus("idle");
      setResult(null);
      return;
    }

    // 200ms デバウンス + AbortController で前のリクエストをキャンセル
    const controller = new AbortController();

    const timer = setTimeout(async () => {
      setStatus("searching");

      try {
        const searchResult = await searchPatientsByMrn(query, {
          signal: controller.signal,
        });

        switch (searchResult.kind) {
          case "found":
            setStatus("found");
            setResult(searchResult.patient);
            break;
          case "not_found":
            setStatus("not_found");
            setResult(null);
            break;
          case "error":
            setStatus("error");
            setResult(null);
            break;
        }
      } catch (err) {
        // AbortError はクエリ変更によるキャンセルの正常系 — 状態を変えない
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        setStatus("error");
        setResult(null);
      }
    }, 200);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  return { query, setQuery, status, result };
}
