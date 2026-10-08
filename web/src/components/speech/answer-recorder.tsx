"use client";

import { Keyboard, Mic, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button, Notice, Textarea } from "@/components/ui";
import { formatDuration } from "@/lib/utils";

import { useRecorder, type Recording } from "./use-recorder";
import { Waveform } from "./waveform";

/**
 * Record a spoken answer (with live transcription where supported) or type it instead.
 * `onAnswer` receives the transcript, timing and pause statistics measured from the audio.
 */
export function AnswerRecorder({
  onAnswer,
  busy,
  maxSeconds,
  submitLabel = "Send answer",
}: {
  onAnswer: (answer: Recording) => void | Promise<void>;
  busy?: boolean;
  maxSeconds?: number;
  submitLabel?: string;
}) {
  const recorder = useRecorder();
  const [typing, setTyping] = useState(false);
  const [typed, setTyped] = useState("");
  const [pending, setPending] = useState<Recording | null>(null);

  const recording = recorder.state === "recording";
  const stopping = useRef(false);

  async function stop() {
    if (stopping.current) return;
    stopping.current = true;
    try {
      const result = await recorder.stop();
      if (!result) return;
      if (result.transcript) {
        await onAnswer(result);
      } else {
        // No transcript from the browser: keep the audio and ask the learner to type what they said.
        setPending(result);
        setTyping(true);
      }
    } finally {
      stopping.current = false;
    }
  }

  // Stop automatically when the time limit for this answer is reached.
  const overTime = !!maxSeconds && recording && recorder.elapsed >= maxSeconds;
  useEffect(() => {
    if (overTime) void stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [overTime]);

  async function submitTyped() {
    const text = typed.trim();
    if (!text) return;
    const base: Recording = pending ?? { blob: null, mimeType: "", durationSeconds: 0, transcript: "", transcriptSource: "typed", pauses: null };
    await onAnswer({ ...base, transcript: text, transcriptSource: "typed", durationSeconds: base.durationSeconds });
    setTyped("");
    setPending(null);
    setTyping(false);
  }

  return (
    <div className="space-y-3">
      {recorder.error && <Notice tone="warning">{recorder.error}</Notice>}
      {!typing && (
        <div className="rounded-2xl border border-border bg-muted/40 p-4">
          <Waveform levels={recorder.levels} active={recording} />
          <div className="mt-3 flex flex-wrap items-center gap-3">
            {recording ? (
              <Button variant="danger" onClick={stop} disabled={busy}>
                <Square className="size-4" /> Stop &amp; send
              </Button>
            ) : (
              <Button onClick={() => recorder.start()} loading={recorder.state === "requesting" || busy}>
                <Mic className="size-4" /> {busy ? "Sending…" : "Start recording"}
              </Button>
            )}
            <span className="font-mono text-sm tabular-nums text-muted-foreground">
              {formatDuration(recorder.elapsed)}
              {maxSeconds ? ` / ${formatDuration(maxSeconds)}` : ""}
            </span>
            <Button variant="ghost" size="sm" onClick={() => setTyping(true)} disabled={recording || busy}>
              <Keyboard className="size-4" /> Type instead
            </Button>
          </div>
          {recording && (
            <p className="mt-3 min-h-6 text-sm text-muted-foreground" aria-live="polite">
              {recorder.liveTranscript || "Listening… (live transcript appears here when your browser supports it)"}
            </p>
          )}
        </div>
      )}
      {typing && (
        <div className="space-y-2">
          {pending && <Notice tone="primary">Your recording was saved, but this browser didn&apos;t provide a transcript. Please type what you said.</Notice>}
          <Textarea rows={4} value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="Type your answer as you would say it…" aria-label="Your answer" />
          <div className="flex gap-2">
            <Button onClick={submitTyped} disabled={!typed.trim()} loading={busy}>
              {submitLabel}
            </Button>
            {!pending && (
              <Button variant="ghost" onClick={() => setTyping(false)}>
                <Mic className="size-4" /> Record instead
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
