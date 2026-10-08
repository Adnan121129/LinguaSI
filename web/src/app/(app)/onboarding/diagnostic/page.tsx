"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, ChevronLeft, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { BandValue } from "@/components/band";
import { ChoiceList } from "@/components/choice-list";
import { SIActions, useToast } from "@/components/providers/toast";
import { AnswerRecorder } from "@/components/speech/answer-recorder";
import { ListeningPlayer } from "@/components/speech/listening-player";
import { Badge, Button, Card, CardBody, CardHeader, ErrorState, Notice, PageSkeleton, ProgressBar, Textarea, buttonClasses } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { DiagnosticItem, DiagnosticResult, DiagnosticStart } from "@/lib/types";
import { wordCount } from "@/lib/utils";

const SECTIONS = ["Vocabulary", "Grammar", "Reading", "Listening", "Writing", "Speaking"] as const;

function ItemList({ items, answers, setAnswer }: { items: DiagnosticItem[]; answers: Record<string, string>; setAnswer: (id: string, v: string) => void }) {
  return (
    <ol className="space-y-6">
      {items.map((item, index) => (
        <li key={item.id} className="space-y-2">
          <p className="font-medium">
            <span className="mr-2 text-muted-foreground">{index + 1}.</span>
            {item.prompt}
          </p>
          <ChoiceList name={item.id} options={item.options ?? []} value={answers[item.id]} onChange={(v) => setAnswer(item.id, v)} />
        </li>
      ))}
    </ol>
  );
}

function ResultView({ result }: { result: DiagnosticResult }) {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <p className="flex items-center gap-2 text-sm font-medium text-primary">
          <CheckCircle2 className="size-4" /> Diagnostic complete
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">Your starting point</h1>
      </div>
      <Card>
        <CardBody className="flex flex-wrap items-center gap-8">
          <BandValue band={result.estimated_band} size="xl" label={result.label} />
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">AI Estimated Level</p>
            <p className="text-4xl font-semibold">{result.estimated_cefr ?? "—"}</p>
          </div>
          <Badge tone={result.confidence === "high" ? "success" : result.confidence === "medium" ? "primary" : "warning"}>{result.confidence} confidence</Badge>
        </CardBody>
        <div className="border-t border-border px-5 py-3 text-xs text-muted-foreground">{result.disclaimer}</div>
      </Card>

      <Card>
        <CardHeader title="Section results" />
        <CardBody>
          <div className="grid gap-4 sm:grid-cols-2">
            {result.sections.map((s) => (
              <div key={s.key} className="space-y-1.5">
                <div className="flex justify-between text-sm">
                  <span className="font-medium">{s.label}</span>
                  <span className="text-muted-foreground">
                    {s.band !== null && s.band !== undefined ? `Band ${s.band}` : s.score !== null ? `${Math.round(s.score)}/100` : "Not taken"}
                    {s.total ? ` · ${s.correct}/${s.total}` : ""}
                  </span>
                </div>
                <ProgressBar value={s.score ?? 0} />
                {s.note && <p className="text-xs text-muted-foreground">{s.note}</p>}
              </div>
            ))}
          </div>
        </CardBody>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader title="Strengths" />
          <CardBody>
            <ul className="list-inside list-disc space-y-1 text-sm">{result.strengths.map((s) => <li key={s}>{s}</li>)}</ul>
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Focus areas" />
          <CardBody>
            <ul className="list-inside list-disc space-y-1 text-sm">{result.focus_areas.map((s) => <li key={s}>{s}</li>)}</ul>
          </CardBody>
        </Card>
      </div>

      {result.writing_feedback && (
        <Card>
          <CardHeader title="Writing sample" description={result.writing_feedback.summary} />
          {result.writing_feedback.top_errors.length > 0 && (
            <CardBody>
              <ul className="space-y-2 text-sm">
                {result.writing_feedback.top_errors.map((e) => (
                  <li key={e.original}>
                    <span className="mark-error">{e.original}</span> → <span className="font-medium text-success">{e.corrected}</span>
                    {e.explanation && <span className="text-muted-foreground"> — {e.explanation}</span>}
                  </li>
                ))}
              </ul>
            </CardBody>
          )}
        </Card>
      )}

      <SIActions outcome={result.outcome} />

      <Card>
        <CardHeader title="Your next steps" icon={<Sparkles className="size-4" />} />
        <CardBody className="space-y-3">
          {result.next_steps.map((step) => (
            <Link key={step.title} href={step.route} className="flex items-center justify-between gap-3 rounded-xl border border-border p-3 hover:bg-muted">
              <span>
                <span className="block font-medium">{step.title}</span>
                <span className="block text-sm text-muted-foreground">{step.why}</span>
              </span>
              <ArrowRight className="size-4 shrink-0 text-muted-foreground" />
            </Link>
          ))}
          <Link href="/dashboard" className={buttonClasses("primary", "md", "w-full")}>
            Go to my dashboard
          </Link>
        </CardBody>
      </Card>
    </div>
  );
}

export default function DiagnosticPage() {
  const queryClient = useQueryClient();
  const { push, celebrate } = useToast();
  const [section, setSection] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [writing, setWriting] = useState("");
  const [speaking, setSpeaking] = useState<Record<string, { transcript: string; duration_seconds: number; source: string }>>({});
  const start = useQuery({ queryKey: ["diagnostic-start"], queryFn: () => api<DiagnosticStart>("/diagnostic/start", { method: "POST" }), staleTime: Infinity, retry: 1 });
  const submit = useMutation({
    mutationFn: (attemptId: number) =>
      api<DiagnosticResult>(`/diagnostic/${attemptId}/submit`, {
        json: { answers, writing, speaking: Object.entries(speaking).map(([id, s]) => ({ id, ...s })) },
      }),
    onSuccess: (result) => {
      celebrate(result.outcome);
      queryClient.invalidateQueries({ queryKey: ["me"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (err) => push({ tone: "error", title: "We couldn't score your diagnostic", description: errorMessage(err) }),
  });

  if (submit.data) return <ResultView result={submit.data} />;
  if (start.isLoading) return <PageSkeleton />;
  if (start.error || !start.data) return <ErrorState error={start.error} onRetry={() => start.refetch()} />;
  const data = start.data;
  const setAnswer = (id: string, v: string) => setAnswers((a) => ({ ...a, [id]: v }));
  const words = wordCount(writing);
  const last = section === SECTIONS.length - 1;

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6">
        <p className="text-sm font-medium text-primary">Diagnostic · about 15 minutes</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">{SECTIONS[section]}</h1>
        <div className="mt-4 flex flex-wrap gap-1.5" aria-label="Sections">
          {SECTIONS.map((name, i) => (
            <button key={name} onClick={() => setSection(i)} className={`rounded-full px-3 py-1 text-xs font-medium ${i === section ? "bg-primary text-primary-foreground" : i < section ? "bg-primary-soft text-primary" : "bg-muted text-muted-foreground"}`}>
              {name}
            </button>
          ))}
        </div>
      </div>

      <Card>
        <CardBody className="space-y-6">
          {section === 0 && <ItemList items={data.vocabulary} answers={answers} setAnswer={setAnswer} />}
          {section === 1 && <ItemList items={data.grammar} answers={answers} setAnswer={setAnswer} />}
          {section === 2 && (
            <>
              <article className="rounded-2xl bg-muted/50 p-4">
                <h2 className="mb-2 font-semibold">{data.reading.title}</h2>
                <p className="whitespace-pre-line text-sm leading-relaxed">{data.reading.text}</p>
              </article>
              <ItemList items={data.reading.questions} answers={answers} setAnswer={setAnswer} />
            </>
          )}
          {section === 3 && (
            <>
              <p className="text-sm text-muted-foreground">
                {data.listening.title}. Listen to the conversation (you can play it twice), then answer the questions.
              </p>
              <ListeningPlayer segments={data.listening.segments} speakers={data.listening.speakers} rate={0.95} maxPlays={2} />
              <details className="text-sm text-muted-foreground">
                <summary className="cursor-pointer">Can&apos;t play audio? Show the transcript</summary>
                <div className="mt-2 space-y-1">
                  {data.listening.segments.map((s, i) => (
                    <p key={i}>
                      <span className="font-medium">{data.listening.speakers.find((sp) => sp.id === s.speaker)?.name ?? s.speaker}:</span> {s.text}
                    </p>
                  ))}
                </div>
              </details>
              <ItemList items={data.listening.questions} answers={answers} setAnswer={setAnswer} />
            </>
          )}
          {section === 4 && (
            <div className="space-y-3">
              <p className="font-medium">{data.writing.prompt}</p>
              <p className="text-sm text-muted-foreground">
                Aim for at least {data.writing.min_words} words (about {data.writing.time_limit_minutes} minutes). Write naturally — this shows SI where to start.
              </p>
              <Textarea rows={12} value={writing} onChange={(e) => setWriting(e.target.value)} aria-label="Your writing" />
              <p className={`text-sm ${words >= data.writing.min_words ? "text-success" : "text-muted-foreground"}`}>{words} words</p>
            </div>
          )}
          {section === 5 && (
            <div className="space-y-6">
              <Notice tone="primary">Answer each question in 3–4 sentences. Recording is optional — you can type your answers instead.</Notice>
              {data.speaking.map((prompt) => (
                <div key={prompt.id} className="space-y-2">
                  <p className="font-medium">{prompt.prompt}</p>
                  {speaking[prompt.id] ? (
                    <div className="rounded-xl bg-success-soft p-3 text-sm">
                      <p className="font-medium text-success">Answer saved</p>
                      <p className="mt-1">{speaking[prompt.id].transcript}</p>
                      <button className="mt-2 text-xs text-primary underline" onClick={() => setSpeaking(({ [prompt.id]: _removed, ...rest }) => rest)}>
                        Answer again
                      </button>
                    </div>
                  ) : (
                    <AnswerRecorder
                      submitLabel="Save answer"
                      maxSeconds={60}
                      onAnswer={(rec) =>
                        setSpeaking((s) => ({ ...s, [prompt.id]: { transcript: rec.transcript, duration_seconds: rec.durationSeconds, source: rec.transcriptSource } }))
                      }
                    />
                  )}
                </div>
              ))}
            </div>
          )}
        </CardBody>
      </Card>

      <div className="mt-6 flex items-center justify-between">
        <Button variant="ghost" disabled={section === 0} onClick={() => setSection((s) => s - 1)}>
          <ChevronLeft className="size-4" /> Back
        </Button>
        {last ? (
          <Button onClick={() => submit.mutate(data.attempt_id)} loading={submit.isPending}>
            See my results
          </Button>
        ) : (
          <Button onClick={() => setSection((s) => s + 1)}>
            Next section <ArrowRight className="size-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
