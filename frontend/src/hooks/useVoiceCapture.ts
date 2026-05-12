"use client";

/**
 * useVoiceCapture フック — マイク録音 → 文字起こし状態機械。
 *
 * 状態遷移:
 *   idle → permission-requested → recording → stopping → uploading → success | error
 *   任意の状態 → cancel() → idle
 *
 * PHI ルール (local-llm-and-phi.md §3/§4):
 * - audio Blob は useRef に保持し、localStorage / sessionStorage / IndexedDB に書かない。
 * - encounterId / transcript を console.* に出力しない。
 *
 * MediaRecorder 制約:
 * - AUDIO_MIME_TYPE (audio/webm;codecs=opus) のサポートを start() 冒頭で確認する。
 * - 60 秒 (AUDIO_MAX_DURATION_S) で自動停止する。
 */

import { useState, useRef, useCallback, useEffect } from "react";
import { transcribeAudio } from "@/services/asr";
import { AUDIO_MIME_TYPE, AUDIO_MAX_DURATION_S, VOICE_CAPTURE_ERRORS } from "@/lib/constants";

export type VoiceCaptureStatus =
  | "idle"
  | "permission-requested"
  | "recording"
  | "stopping"
  | "uploading"
  | "success"
  | "error";

export interface VoiceCaptureError {
  kind:
    | "permissionDenied"
    | "transcriptionUnavailable"
    | "transcriptionTimeout"
    | "unsupportedCodec"
    | "generic";
  message: string;
}

export interface UseVoiceCaptureReturn {
  status: VoiceCaptureStatus;
  /** 録音開始からの経過ミリ秒 (recording / uploading 中に更新される) */
  elapsedMs: number;
  /** 文字起こし成功テキスト (PHI — ログに出力しない) */
  transcript: string;
  /** エラー詳細 (status === "error" のとき設定される) */
  error: VoiceCaptureError | null;
  start: () => Promise<void>;
  stop: () => void;
  cancel: () => void;
}

export function useVoiceCapture(encounterId: string): UseVoiceCaptureReturn {
  const [status, setStatus] = useState<VoiceCaptureStatus>("idle");
  const [elapsedMs, setElapsedMs] = useState(0);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<VoiceCaptureError | null>(null);

  // PHI: audio Blob は useRef に保持し、React state に入れない (DevTools スナップショット回避)
  const chunksRef = useRef<Blob[]>([]);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(0);

  /** 内部クリーンアップ — recorder / stream / interval / abort を解放する */
  const cleanup = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      try {
        recorderRef.current.stop();
      } catch {
        // すでに停止済みの場合は無視する
      }
    }
    recorderRef.current = null;
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    chunksRef.current = [];
  }, []);

  /** アンマウント時にクリーンアップする */
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      cleanup();
    };
  }, [cleanup]);

  /** 経過時間カウンターを開始する */
  const startTimer = useCallback(() => {
    startTimeRef.current = Date.now();
    setElapsedMs(0);
    intervalRef.current = setInterval(() => {
      setElapsedMs(Date.now() - startTimeRef.current);
    }, 100);
  }, []);

  const start = useCallback(async () => {
    // コーデックサポート確認
    if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported(AUDIO_MIME_TYPE)) {
      setError({
        kind: "unsupportedCodec",
        message: VOICE_CAPTURE_ERRORS.unsupportedCodec,
      });
      setStatus("error");
      return;
    }

    setStatus("permission-requested");
    setError(null);
    setTranscript("");

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError({
        kind: "permissionDenied",
        message: VOICE_CAPTURE_ERRORS.permissionDenied,
      });
      setStatus("error");
      return;
    }

    streamRef.current = stream;
    chunksRef.current = [];

    const recorder = new MediaRecorder(stream, { mimeType: AUDIO_MIME_TYPE });
    recorderRef.current = recorder;

    recorder.ondataavailable = (e: BlobEvent) => {
      if (e.data.size > 0) {
        chunksRef.current.push(e.data);
      }
    };

    recorder.onstop = () => {
      // チャンクを結合して Blob を作成し、アップロードする
      const blob = new Blob(chunksRef.current, { type: AUDIO_MIME_TYPE });
      chunksRef.current = [];

      // ストリームトラックを停止する
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }

      // intervalRef は stopTimer/cancel で別途クリアされるが、念のためここでも確認する
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }

      setStatus("uploading");
      startTimeRef.current = Date.now();
      setElapsedMs(0);
      // uploading 中も経過時間を更新する (キャンセルボタン出現に使う)
      intervalRef.current = setInterval(() => {
        setElapsedMs(Date.now() - startTimeRef.current);
      }, 100);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      void transcribeAudio(encounterId, blob, { signal: controller.signal })
        .then((result) => {
          if (intervalRef.current !== null) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }

          if (result.kind === "success") {
            setTranscript(result.text);
            setStatus("success");
          } else if (result.kind === "transcription_unavailable") {
            setError({
              kind: "transcriptionUnavailable",
              message: VOICE_CAPTURE_ERRORS.transcriptionUnavailable,
            });
            setStatus("error");
          } else if (result.kind === "transcription_timeout") {
            setError({
              kind: "transcriptionTimeout",
              message: VOICE_CAPTURE_ERRORS.transcriptionTimeout,
            });
            setStatus("error");
          } else if (result.kind === "unsupported_format") {
            setError({ kind: "unsupportedCodec", message: VOICE_CAPTURE_ERRORS.unsupportedCodec });
            setStatus("error");
          } else {
            // encounter_not_found / validation_error / error
            setError({ kind: "generic", message: VOICE_CAPTURE_ERRORS.generic });
            setStatus("error");
          }
        })
        .catch((err: unknown) => {
          // AbortError はキャンセルの正常系 — idle に戻す (cancel() が処理する)
          if (err instanceof DOMException && err.name === "AbortError") {
            return;
          }
          if (intervalRef.current !== null) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
          setError({ kind: "generic", message: VOICE_CAPTURE_ERRORS.generic });
          setStatus("error");
        });
    };

    recorder.start();
    setStatus("recording");
    startTimer();
  }, [encounterId, startTimer]);

  const stop = useCallback(() => {
    setStatus("stopping");
    if (recorderRef.current && recorderRef.current.state === "recording") {
      recorderRef.current.stop();
      // onstop ハンドラが uploading への遷移と transcribeAudio 呼び出しを担当する
    }
    // intervalRef は onstop ハンドラ内でリセットされる
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const cancel = useCallback(() => {
    // 進行中のアップロードをキャンセルする
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    cleanup();
    setElapsedMs(0);
    setStatus("idle");
  }, [cleanup]);

  // 60 秒自動停止 — recording 中に AUDIO_MAX_DURATION_S を超えたら stop() を呼ぶ
  useEffect(() => {
    if (status === "recording" && elapsedMs >= AUDIO_MAX_DURATION_S * 1000) {
      stop();
    }
  }, [status, elapsedMs, stop]);

  return { status, elapsedMs, transcript, error, start, stop, cancel };
}

export default useVoiceCapture;
