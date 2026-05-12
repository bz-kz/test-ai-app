"use client";

/**
 * useVoiceCapture フック — マイク録音 → 文字起こし状態機械。
 *
 * 状態遷移:
 *   idle → requesting_permission → recording → uploading → success | error | permission_denied
 *   任意の状態 → cancel() → idle
 *
 * FE-013 ストリーミング拡張 (ADR-0003):
 *   ASR_STREAMING_ENABLED (モジュールスコープ定数) が true のとき、
 *   recorder.onstop は streamTranscribeAudio を呼ぶ。
 *   返り値の shape に `streaming` フィールドが追加される。
 *   streaming フィールドは、ストリーミングパスがアクティブかつ少なくとも 1 チャンク
 *   が届いている間だけ非 null になる。
 *
 *   チャンクテキストの蓄積は useRef<string[]> に行う (PHI — React state に入れると
 *   DevTools のスナップショットで露出するリスクがある)。
 *   streaming.partialText は onChunk のたびに tick カウンタ (useState<number>) を
 *   インクリメントして再レンダーをトリガーし、ref から読み取って導出する。
 *
 * PHI ルール (local-llm-and-phi.md §3/§4):
 * - audio Blob は useRef に保持し、localStorage / sessionStorage / IndexedDB に書かない。
 * - encounterId / transcript / チャンクテキスト を console.* に出力しない。
 *
 * MediaRecorder 制約:
 * - AUDIO_MIME_TYPE (audio/webm;codecs=opus) のサポートを start() 冒頭で確認する。
 * - 60 秒 (AUDIO_MAX_DURATION_S) で自動停止する。
 */

import { useState, useRef, useCallback, useEffect } from "react";
import { transcribeAudio } from "@/services/transcribe";
import { streamTranscribeAudio } from "@/services/transcribe";
import {
  AUDIO_MIME_TYPE,
  AUDIO_MAX_DURATION_S,
  VOICE_CAPTURE_ERRORS,
  ASR_STREAMING_ENABLED,
} from "@/lib/constants";

export type VoiceCaptureStatus =
  | "idle"
  | "requesting_permission"
  | "recording"
  | "uploading"
  | "success"
  | "error"
  | "permission_denied";

export interface VoiceCaptureError {
  kind:
    | "permissionDenied"
    | "transcriptionUnavailable"
    | "transcriptionTimeout"
    | "unsupportedCodec"
    | "generic";
  message: string;
}

/**
 * ストリーミングパスがアクティブかつ少なくとも 1 チャンクが届いているときに非 null。
 * partialText: チャンクバッファから導出した結合文字列 (PHI — React state ではなく ref から取得)。
 */
export interface StreamingInfo {
  chunkIndex: number;
  chunkCount: number;
  partialText: string;
}

export interface UseVoiceCaptureReturn {
  status: VoiceCaptureStatus;
  /** 録音開始からの経過ミリ秒 (recording / uploading 中に更新される) */
  elapsedMs: number;
  /** 文字起こし成功テキスト (PHI — ログに出力しない) */
  transcript: string;
  /** エラー詳細 (status === "error" のとき設定される) */
  error: VoiceCaptureError | null;
  /** 60 秒自動停止かどうかのフラグ (VoiceCapture で toast 表示に使う) */
  autoStopped: boolean;
  /**
   * ストリーミングパスが有効かつ 1 チャンク以上届いているとき非 null。
   * null = 非ストリーミングパス、または最初のチャンク未着。
   */
  streaming: StreamingInfo | null;
  start: () => Promise<void>;
  stop: () => void;
  cancel: () => void;
}

export function useVoiceCapture(encounterId: string): UseVoiceCaptureReturn {
  const [status, setStatus] = useState<VoiceCaptureStatus>("idle");
  const [elapsedMs, setElapsedMs] = useState(0);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<VoiceCaptureError | null>(null);
  const [autoStopped, setAutoStopped] = useState(false);

  // ストリーミング状態: chunk 到着で再レンダーをトリガーするカウンタ
  const [streaming, setStreaming] = useState<StreamingInfo | null>(null);

  // PHI: audio Blob / チャンクバッファは useRef に保持する (DevTools スナップショット回避)
  const chunksRef = useRef<Blob[]>([]);
  const chunkTextBufRef = useRef<string[]>([]);
  const lastChunkInfoRef = useRef<{ chunkIndex: number; chunkCount: number } | null>(null);

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
    chunkTextBufRef.current = [];
    lastChunkInfoRef.current = null;
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

    setStatus("requesting_permission");
    setError(null);
    setTranscript("");
    setAutoStopped(false);
    setStreaming(null);

    let stream: MediaStream;
    try {
      // モノラル (channelCount: 1) を要求してペイロードを ≤2 MB に収める
      stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1 } });
    } catch {
      // マイク権限拒否 → permission_denied 状態へ遷移
      setStatus("permission_denied");
      return;
    }

    streamRef.current = stream;
    chunksRef.current = [];
    chunkTextBufRef.current = [];
    lastChunkInfoRef.current = null;

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

      if (ASR_STREAMING_ENABLED) {
        // ストリーミングパス (FE-013 / ADR-0003)
        void streamTranscribeAudio(encounterId, blob, {
          signal: controller.signal,

          onChunk: (text, chunkIndex, chunkCount) => {
            // PHI: text を console.* に出力しない
            chunkTextBufRef.current.push(text);
            lastChunkInfoRef.current = { chunkIndex, chunkCount };
            // ref から導出した partialText で streaming state を更新し再レンダーをトリガーする
            setStreaming({
              chunkIndex,
              chunkCount,
              partialText: chunkTextBufRef.current.join(""),
            });
          },

          onComplete: (info) => {
            if (intervalRef.current !== null) {
              clearInterval(intervalRef.current);
              intervalRef.current = null;
            }
            // PHI: fullText を console.* に出力しない
            setTranscript(info.fullText);
            setStreaming(null);
            chunkTextBufRef.current = [];
            lastChunkInfoRef.current = null;
            setStatus("success");
          },

          onError: (info) => {
            if (intervalRef.current !== null) {
              clearInterval(intervalRef.current);
              intervalRef.current = null;
            }
            chunkTextBufRef.current = [];
            lastChunkInfoRef.current = null;
            setStreaming(null);

            if (info.kind === "transcription_unavailable") {
              setError({
                kind: "transcriptionUnavailable",
                message: VOICE_CAPTURE_ERRORS.transcriptionUnavailable,
              });
            } else if (info.kind === "transcription_timeout") {
              setError({
                kind: "transcriptionTimeout",
                message: VOICE_CAPTURE_ERRORS.transcriptionTimeout,
              });
            } else if (info.kind === "unsupported_format") {
              setError({
                kind: "unsupportedCodec",
                message: VOICE_CAPTURE_ERRORS.unsupportedCodec,
              });
            } else {
              // encounter_not_found / validation_error / error
              setError({ kind: "generic", message: VOICE_CAPTURE_ERRORS.generic });
            }
            setStatus("error");
          },
        }).catch((err: unknown) => {
          // AbortError はキャンセルの正常系 — cancel() が処理する
          if (err instanceof DOMException && err.name === "AbortError") {
            return;
          }
          if (intervalRef.current !== null) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
          chunkTextBufRef.current = [];
          lastChunkInfoRef.current = null;
          setStreaming(null);
          setError({ kind: "generic", message: VOICE_CAPTURE_ERRORS.generic });
          setStatus("error");
        });
      } else {
        // 非ストリーミングパス (FE-009 の動作を維持する)
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
              setError({
                kind: "unsupportedCodec",
                message: VOICE_CAPTURE_ERRORS.unsupportedCodec,
              });
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
      }
    };

    recorder.start();
    setStatus("recording");
    startTimer();
  }, [encounterId, startTimer]);

  const stop = useCallback(() => {
    if (recorderRef.current && recorderRef.current.state === "recording") {
      recorderRef.current.stop();
      // onstop ハンドラが uploading への遷移と transcribeAudio/streamTranscribeAudio 呼び出しを担当する
    }
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const cancel = useCallback(() => {
    // 進行中のアップロード/ストリームをキャンセルする
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    // チャンクバッファを破棄し streaming を null にリセットする
    chunkTextBufRef.current = [];
    lastChunkInfoRef.current = null;
    setStreaming(null);
    cleanup();
    setElapsedMs(0);
    setAutoStopped(false);
    setStatus("idle");
  }, [cleanup]);

  // 60 秒自動停止 — recording 中に AUDIO_MAX_DURATION_S を超えたら stop() を呼ぶ
  useEffect(() => {
    if (status === "recording" && elapsedMs >= AUDIO_MAX_DURATION_S * 1000) {
      // 自動停止フラグを立ててから stop する
      setAutoStopped(true);
      stop();
    }
  }, [status, elapsedMs, stop]);

  return { status, elapsedMs, transcript, error, autoStopped, streaming, start, stop, cancel };
}

export default useVoiceCapture;
