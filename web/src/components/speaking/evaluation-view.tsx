"use client";

import { Info, Volume2 } from "lucide-react";

import { BandValue, CriterionBar } from "@/components/band";
import { Badge, Card, CardBody, CardHeader } from "@/components/ui";
import { mediaUrl } from "@/lib/api";
import type { SpeakingSession } from "@/lib/types";
import { formatDuration } from "@/lib/utils";

function Bullets({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <p className="text-sm font-semibold">{title}</p>
      <ul className="mt-2 list-inside list-disc space-y-1 text-sm">{items.map((i) => <li key={i}>{i}</li>)}</ul>
    </div>
  );
}

export function SpeakingEvaluationView({ session }: { session: SpeakingSession }) {
  const ev = session.evaluation!;
  const metrics = ev.metrics as Record<string, number | boolean | null>;
  const criteria = ["fluency_coherence", "lexical_resource", "grammatical_range_accuracy", "pronunciation"] as const;
  return (
    <div className="space-y-6">
      <Card>
        <CardBody className="flex flex-wrap items-center gap-6">
          <BandValue band={ev.overall_band} size="xl" label={ev.label} />
          <div className="min-w-0 flex-1 space-y-2">
            <p className="text-sm">{ev.summary}</p>
            <div className="flex flex-wrap gap-2">
              <Badge>{session.mode === "full" ? "Full mock test" : `Part ${session.mode.slice(-1)}`}</Badge>
              <Badge>{session.transcripts.length} answers</Badge>
              <Badge>{formatDuration(session.total_speaking_seconds)} speaking</Badge>
              {ev.is_mock && <Badge tone="warning">Mock AI Mode analysis</Badge>}
            </div>
          </div>
        </CardBody>
        <p className="border-t border-border px-5 py-3 text-xs text-muted-foreground">{ev.disclaimer}</p>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Criteria" description="Estimated from your transcripts and measured speech features." />
          <CardBody className="space-y-4">
            {criteria.map((key) => {
              const fb = ev.criteria_feedback[key];
              const band = key === "pronunciation" ? ev.pronunciation : ev[key];
              return <CriterionBar key={key} label={fb?.label ?? key} band={band} comment={fb?.comment} />;
            })}
            {ev.pronunciation === null && (
              <p className="flex items-start gap-1.5 rounded-xl bg-muted p-3 text-xs text-muted-foreground">
                <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden /> {ev.pronunciation_note}
              </p>
            )}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Fluency measurements" description={ev.hesitation.note} />
          <CardBody>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              {[
                ["Speaking speed", metrics.avg_wpm ? `${Math.round(Number(metrics.avg_wpm))} words/min` : "—"],
                ["Hesitation", ev.hesitation.level],
                [ev.hesitation.measured ? "Pauses (measured)" : "Pauses (estimated)", `${ev.hesitation.pauses} · ${ev.hesitation.long_pauses} long`],
                ["Filler words", `${ev.fillers.per_minute}/min`],
                ["Developed answers", metrics.developed_ratio !== undefined && metrics.developed_ratio !== null ? `${Math.round(Number(metrics.developed_ratio) * 100)}%` : "—"],
                ["Word variety", metrics.lexical_variety ?? "—"],
              ].map(([label, value]) => (
                <div key={String(label)} className="rounded-xl bg-muted p-3">
                  <dt className="text-xs text-muted-foreground">{label}</dt>
                  <dd className="font-semibold capitalize">{String(value)}</dd>
                </div>
              ))}
            </dl>
            {ev.repeated_words.length > 0 && (
              <p className="mt-3 text-sm text-muted-foreground">Most repeated words: {ev.repeated_words.slice(0, 5).map((w) => `${w.word} (${w.count})`).join(", ")}</p>
            )}
            <p className="mt-2 text-xs text-muted-foreground">{ev.fillers.note}</p>
          </CardBody>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardBody className="space-y-5">
            <Bullets title="Strengths" items={ev.strengths} />
            <Bullets title="To improve" items={ev.weaknesses} />
          </CardBody>
        </Card>
        <Card>
          <CardBody className="space-y-5">
            <Bullets title="Grammar patterns" items={ev.grammar_patterns} />
            <Bullets title="Practice recommendations" items={ev.recommendations} />
            {ev.expressions_used.length > 0 && <Bullets title="Target expressions you used" items={ev.expressions_used} />}
          </CardBody>
        </Card>
      </div>

      {ev.errors.length > 0 && (
        <Card>
          <CardHeader title="Language to fix" description="These are saved to My Mistakes." />
          <CardBody>
            <ul className="space-y-2 text-sm">
              {ev.errors.map((e, i) => (
                <li key={i}>
                  <span className="mark-error">{e.original}</span> → <span className="font-medium text-success">{e.corrected}</span>
                  <span className="text-muted-foreground"> — {e.explanation}</span>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader title="Your answers" description="Replay your recordings and read the transcripts." />
        <CardBody>
          <ol className="space-y-4">
            {session.transcripts.map((t) => (
              <li key={t.id} className="rounded-xl border border-border p-4">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Part {t.part}
                  {t.is_followup ? " · follow-up" : ""} · {Math.round(t.duration_seconds)}s · {t.word_count} words · {t.transcript_source === "typed" ? "typed" : "spoken"}
                </p>
                <p className="mt-1 font-medium">{t.question}</p>
                <p className="mt-2 text-sm leading-relaxed">{t.transcript}</p>
                {t.has_audio && t.audio_url && (
                  <div className="mt-3 flex items-center gap-2">
                    <Volume2 className="size-4 text-muted-foreground" aria-hidden />
                    <audio controls preload="none" src={mediaUrl(t.audio_url) ?? undefined} className="h-9 w-full max-w-md" aria-label={`Recording for: ${t.question}`} />
                  </div>
                )}
              </li>
            ))}
          </ol>
        </CardBody>
      </Card>
    </div>
  );
}
