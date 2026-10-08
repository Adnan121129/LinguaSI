"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Info, Mic, Square, Volume2 } from "lucide-react";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

import { useToast } from "@/components/providers/toast";
import { Badge, Button, Card, CardBody, CardHeader, ErrorState, Notice, PageHeader, PageSkeleton, ProgressBar, Tabs } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { recognitionConstructor, recognitionSupported, speak, ttsSupported, type Recognizer } from "@/lib/speech";
import type { PronunciationResult } from "@/lib/types";

type PronunciationSet = { focus: string; title: string; sentences: string[] };
const subscribe = () => () => {};

function SentencePractice({ sentence }: { sentence: string }) {
  const { push, celebrate } = useToast();
  const [listening, setListening] = useState(false);
  const recognizer = useRef<Recognizer | null>(null);
  const started = useRef(0);
  const check = useMutation({
    mutationFn: (transcript: string) => api<PronunciationResult>("/lab/pronunciation/check", { json: { sentence, transcript, duration_seconds: (Date.now() - started.current) / 1000 } }),
    onSuccess: (res) => celebrate(res.outcome),
    onError: (err) => push({ tone: "error", title: "Couldn't check that attempt", description: errorMessage(err) }),
  });

  useEffect(() => () => recognizer.current?.abort(), []);

  function record() {
    const Recognition = recognitionConstructor();
    if (!Recognition) return;
    const r = new Recognition();
    r.lang = "en-GB";
    r.continuous = false;
    r.interimResults = false;
    r.onresult = (event) => {
      const transcript = Array.from({ length: event.results.length }, (_, i) => event.results[i][0].transcript).join(" ");
      check.mutate(transcript);
    };
    r.onerror = (event) => push({ tone: "warning", title: "We didn't catch that", description: event.error === "not-allowed" ? "Allow the microphone to use pronunciation practice." : "Try again a little closer to the microphone." });
    r.onend = () => setListening(false);
    recognizer.current = r;
    started.current = Date.now();
    setListening(true);
    r.start();
  }

  const result = check.data;
  const missing = new Set(result?.missing_words.map((w) => w.toLowerCase()));
  return (
    <div className="space-y-3 rounded-xl border border-border p-4">
      <p className="text-lg">
        {sentence.split(" ").map((word, i) => {
          const clean = word.replace(/[^A-Za-z']/g, "").toLowerCase();
          return (
            <span key={i} className={result && missing.has(clean) ? "mark-error" : undefined}>
              {word}{" "}
            </span>
          );
        })}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" onClick={() => speak(sentence, { rate: 0.9 })} disabled={!ttsSupported()}>
          <Volume2 className="size-4" /> Listen
        </Button>
        {listening ? (
          <Button variant="danger" size="sm" onClick={() => recognizer.current?.stop()}>
            <Square className="size-4" /> Stop
          </Button>
        ) : (
          <Button size="sm" onClick={record} loading={check.isPending}>
            <Mic className="size-4" /> Say it
          </Button>
        )}
      </div>
      {result && (
        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-3">
            <Badge tone={result.match >= 90 ? "success" : result.match >= 70 ? "primary" : "warning"}>{Math.round(result.match)}% understood</Badge>
            <ProgressBar className="max-w-xs" value={result.match} tone={result.match >= 90 ? "success" : "primary"} label="Words recognised" />
          </div>
          <p>{result.tip}</p>
          {result.unexpected_words.length > 0 && <p className="text-muted-foreground">Heard instead: {result.unexpected_words.join(", ")}</p>}
        </div>
      )}
    </div>
  );
}

export default function PronunciationPage() {
  const sets = useQuery({ queryKey: ["pronunciation-sets"], queryFn: () => api<PronunciationSet[]>("/lab/pronunciation") });
  const supported = useSyncExternalStore(subscribe, recognitionSupported, () => true);
  const [focus, setFocus] = useState<string | null>(null);
  if (sets.isLoading) return <PageSkeleton />;
  if (sets.error || !sets.data) return <ErrorState error={sets.error} onRetry={() => sets.refetch()} />;
  const current = sets.data.find((s) => s.focus === focus) ?? sets.data[0];
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title="Pronunciation practice" description="Listen, repeat, and see which words speech recognition understood as you intended." />
      <Notice tone="default" icon={<Info className="mt-0.5 size-4" />}>
        This is a clarity check: it compares what speech recognition heard with the sentence. It is a useful practice signal, not a phonetic pronunciation score.
      </Notice>
      {!supported && <Notice tone="warning">Speech recognition isn&apos;t available in this browser. You can still listen and repeat — use Chrome or Edge to get feedback.</Notice>}
      <div className="overflow-x-auto">
        <Tabs value={current.focus} onChange={setFocus} items={sets.data.map((s) => ({ value: s.focus, label: s.title.split(" ").slice(0, 3).join(" ") }))} />
      </div>
      <Card>
        <CardHeader title={current.title} />
        <CardBody className="space-y-3">
          {current.sentences.map((sentence) => (
            <SentencePractice key={sentence} sentence={sentence} />
          ))}
        </CardBody>
      </Card>
    </div>
  );
}
