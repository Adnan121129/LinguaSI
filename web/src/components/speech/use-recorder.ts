"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { recognitionConstructor, type Recognizer } from "@/lib/speech";

export type PauseStats = { measured: true; count: number; long_count: number; total_silence_seconds: number };

export type Recording = {
  blob: Blob | null;
  mimeType: string;
  durationSeconds: number;
  transcript: string;
  transcriptSource: "browser" | "typed";
  pauses: PauseStats | null;
};

const SILENCE_RMS = 0.015; // below this level a frame counts as silence
const PAUSE_SECONDS = 0.6; // silences at least this long count as a pause
const LONG_PAUSE_SECONDS = 2.0;

function preferredMimeType(): string {
  if (typeof MediaRecorder === "undefined") return "";
  for (const type of ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"]) {
    if (MediaRecorder.isTypeSupported(type)) return type;
  }
  return "";
}

/**
 * Microphone recording with a live level meter, pause detection measured from the audio signal and
 * live transcription via the browser's speech recognition (when available).
 */
export function useRecorder() {
  const [state, setState] = useState<"idle" | "requesting" | "recording" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [level, setLevel] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [liveTranscript, setLiveTranscript] = useState("");
  const levels = useRef<number[]>([]);

  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const rafRef = useRef<number | null>(null);
  const recognizerRef = useRef<Recognizer | null>(null);
  const finalTextRef = useRef("");
  const startedAtRef = useRef(0);
  const silenceRef = useRef({ start: null as number | null, count: 0, long: 0, total: 0, heardSpeech: false });
  const stopResolver = useRef<((recording: Recording) => void) | null>(null);

  const cleanup = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    recognizerRef.current?.abort();
    recognizerRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    audioCtxRef.current?.close().catch(() => undefined);
    audioCtxRef.current = null;
  }, []);

  // Stop the microphone when the component is hidden or unmounted.
  useEffect(() => cleanup, [cleanup]);

  const start = useCallback(async () => {
    setError(null);
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setState("error");
      setError("Recording isn't supported in this browser. You can type your answer instead.");
      return false;
    }
    setState("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      streamRef.current = stream;
      const mimeType = preferredMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => e.data.size && chunksRef.current.push(e.data);
      recorder.onstop = () => {
        const duration = (performance.now() - startedAtRef.current) / 1000;
        const s = silenceRef.current; // trailing silence after the last word is not counted as a pause
        const blob = chunksRef.current.length ? new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" }) : null;
        const transcript = finalTextRef.current.trim();
        stopResolver.current?.({
          blob,
          mimeType: recorder.mimeType || "audio/webm",
          durationSeconds: Math.round(duration * 10) / 10,
          transcript,
          transcriptSource: "browser",
          pauses: { measured: true, count: s.count, long_count: s.long, total_silence_seconds: Math.round(s.total * 10) / 10 },
        });
        stopResolver.current = null;
        cleanup();
      };
      recorderRef.current = recorder;

      // Level meter + silence detection
      const ctx = new AudioContext();
      audioCtxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      source.connect(analyser);
      const buffer = new Float32Array(analyser.fftSize);
      silenceRef.current = { start: null, count: 0, long: 0, total: 0, heardSpeech: false };
      levels.current = [];
      const tick = () => {
        analyser.getFloatTimeDomainData(buffer);
        let sum = 0;
        for (const v of buffer) sum += v * v;
        const rms = Math.sqrt(sum / buffer.length);
        const now = performance.now();
        const s = silenceRef.current;
        if (rms < SILENCE_RMS) {
          if (s.start === null) s.start = now;
        } else {
          if (s.start !== null && s.heardSpeech) {
            const gap = (now - s.start) / 1000;
            if (gap >= PAUSE_SECONDS) {
              s.count += 1;
              s.total += gap;
              if (gap >= LONG_PAUSE_SECONDS) s.long += 1;
            }
          }
          s.start = null;
          s.heardSpeech = true;
        }
        const normalised = Math.min(1, rms * 8);
        levels.current = [...levels.current.slice(-59), normalised];
        setLevel(normalised);
        setElapsed((now - startedAtRef.current) / 1000);
        rafRef.current = requestAnimationFrame(tick);
      };

      // Live transcription (optional)
      finalTextRef.current = "";
      setLiveTranscript("");
      const Recognition = recognitionConstructor();
      if (Recognition) {
        const recognizer = new Recognition();
        recognizer.lang = "en-GB";
        recognizer.continuous = true;
        recognizer.interimResults = true;
        recognizer.onresult = (event) => {
          let interim = "";
          for (let i = event.resultIndex; i < event.results.length; i++) {
            const result = event.results[i];
            if (result.isFinal) finalTextRef.current += `${result[0].transcript.trim()} `;
            else interim += result[0].transcript;
          }
          setLiveTranscript(`${finalTextRef.current}${interim}`.trim());
        };
        recognizer.onerror = () => undefined; // recognition is a bonus: recording continues regardless
        recognizer.onend = () => {
          // Browsers stop recognition after silence; restart while we are still recording.
          if (recorderRef.current?.state === "recording" && recognizerRef.current === recognizer) {
            try {
              recognizer.start();
            } catch {
              /* already started */
            }
          }
        };
        recognizerRef.current = recognizer;
        try {
          recognizer.start();
        } catch {
          recognizerRef.current = null;
        }
      }

      startedAtRef.current = performance.now();
      recorder.start(1000);
      rafRef.current = requestAnimationFrame(tick);
      setElapsed(0);
      setState("recording");
      return true;
    } catch (err) {
      cleanup();
      setState("error");
      setError(
        err instanceof DOMException && err.name === "NotAllowedError"
          ? "Microphone access was blocked. Allow the microphone in your browser settings, or type your answer instead."
          : "We couldn't start the microphone. You can type your answer instead.",
      );
      return false;
    }
  }, [cleanup]);

  const stop = useCallback((): Promise<Recording | null> => {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state !== "recording") return Promise.resolve(null);
    return new Promise((resolve) => {
      stopResolver.current = (recording) => {
        setState("idle");
        setLevel(0);
        resolve(recording);
      };
      recognizerRef.current?.stop();
      // Give speech recognition a moment to deliver its final result before closing.
      window.setTimeout(() => recorder.stop(), 350);
    });
  }, []);

  return { state, error, level, levels, elapsed, liveTranscript, start, stop, supported: typeof window !== "undefined" && !!navigator.mediaDevices };
}
