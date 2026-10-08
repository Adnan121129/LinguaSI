"use client";

import { Headphones, Pause, Play, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

import { Button, Notice } from "@/components/ui";
import { assignVoices, loadVoices, speak, stopSpeaking, ttsSupported, type SpeakerVoice } from "@/lib/speech";
import { cn } from "@/lib/utils";

export type PlayerSegment = { speaker: string; text: string | null; audio_url?: string | null };

// Speech-synthesis support never changes during a page's lifetime, so there is nothing to subscribe to.
const noSubscription = () => () => {};

/**
 * Plays a listening script: server-generated audio when available, otherwise the device's own
 * voices (a different voice per speaker). Falls back to the transcript when neither is possible.
 */
export function ListeningPlayer({
  segments,
  speakers,
  rate = 1,
  mode = "device",
  maxPlays,
  onPlay,
}: {
  segments: PlayerSegment[];
  speakers: (SpeakerVoice & { name?: string; role?: string })[];
  rate?: number;
  mode?: "server" | "device";
  maxPlays?: number;
  onPlay?: (count: number) => void;
}) {
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState<number | null>(null);
  const [plays, setPlays] = useState(0);
  const deviceVoices = useSyncExternalStore(noSubscription, ttsSupported, () => true);
  const supported = mode === "server" || deviceVoices;
  const cancelled = useRef(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    return () => {
      cancelled.current = true;
      stopSpeaking();
      audioRef.current?.pause();
    };
  }, [mode]);

  const playAudio = (url: string) =>
    new Promise<void>((resolve) => {
      const audio = new Audio(url);
      audio.playbackRate = rate;
      audioRef.current = audio;
      audio.onended = () => resolve();
      audio.onerror = () => resolve();
      audio.play().catch(() => resolve());
    });

  const play = useCallback(async () => {
    if (playing) return;
    cancelled.current = false;
    setPlaying(true);
    const count = plays + 1;
    setPlays(count);
    onPlay?.(count);
    const voices = mode === "device" ? assignVoices(await loadVoices(), speakers) : {};
    for (let i = 0; i < segments.length; i++) {
      if (cancelled.current) break;
      setCurrent(i);
      const seg = segments[i];
      if (mode === "server" && seg.audio_url) await playAudio(seg.audio_url);
      else if (seg.text) await speak(seg.text, { voice: voices[seg.speaker], rate });
      await new Promise((r) => setTimeout(r, 250));
    }
    setCurrent(null);
    setPlaying(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, plays, segments, speakers, rate, mode, onPlay]);

  const stop = () => {
    cancelled.current = true;
    stopSpeaking();
    audioRef.current?.pause();
    setPlaying(false);
    setCurrent(null);
  };

  const limitReached = maxPlays !== undefined && plays >= maxPlays;

  if (!supported) {
    return (
      <Notice tone="warning">
        This browser can&apos;t play audio voices, so the recording is shown as text instead. Read it once, then answer from memory.
      </Notice>
    );
  }

  return (
    <div className="rounded-2xl border border-border bg-muted/40 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="grid size-10 place-items-center rounded-full bg-primary-soft text-primary">
          <Headphones className="size-5" aria-hidden />
        </div>
        <div className="mr-auto">
          <p className="text-sm font-medium">{playing ? `Playing part ${(current ?? 0) + 1} of ${segments.length}` : plays ? "Recording finished" : "Ready to play"}</p>
          <p className="text-xs text-muted-foreground">
            {mode === "server" ? "Studio voices" : "Device voices"} · speed {rate.toFixed(2)}×{maxPlays !== undefined && ` · ${Math.max(0, maxPlays - plays)} play(s) left`}
          </p>
        </div>
        {playing ? (
          <Button variant="outline" onClick={stop}>
            <Pause className="size-4" /> Stop
          </Button>
        ) : (
          <Button onClick={play} disabled={limitReached}>
            {plays ? <RotateCcw className="size-4" /> : <Play className="size-4" />} {plays ? "Play again" : "Play recording"}
          </Button>
        )}
      </div>
      <div className="mt-3 flex gap-1" aria-hidden>
        {segments.map((_, i) => (
          <span key={i} className={cn("h-1.5 flex-1 rounded-full", current === i ? "bg-primary" : current !== null && i < current ? "bg-primary/50" : "bg-border")} />
        ))}
      </div>
    </div>
  );
}
