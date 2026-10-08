"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock, Info } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { BandValue } from "@/components/band";
import { QuestionForm, withEvidence } from "@/components/comprehension/question-form";
import { SIActions, useToast } from "@/components/providers/toast";
import { Badge, Button, Card, CardBody, ErrorState, Notice, PageSkeleton } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { ActivityOutcome, QuestionResult, ReadingAttempt } from "@/lib/types";
import { cn, formatDuration, percent } from "@/lib/utils";

function SpotlightText({ text, words }: { text: string; words: string[] }) {
  if (!words.length) return <>{text}</>;
  const pattern = new RegExp(`\\b(${words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})\\b`, "gi");
  const parts = text.split(pattern);
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <span key={i} className="rounded bg-accent-soft px-0.5 text-accent" title="A word from your vocabulary list">
            {part}
          </span>
        ) : (
          part
        ),
      )}
    </>
  );
}

export default function ReadingAttemptPage() {
  const { id } = useParams<{ id: string }>();
  const attemptId = Number(id);
  const queryClient = useQueryClient();
  const { push, celebrate } = useToast();
  const { data, error, isLoading, refetch } = useQuery({ queryKey: ["reading-attempt", attemptId], queryFn: () => api<ReadingAttempt>(`/reading/attempts/${attemptId}`), staleTime: Infinity });
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [evidence, setEvidence] = useState<QuestionResult | null>(null);
  const [outcome, setOutcome] = useState<ActivityOutcome | null>(null);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!data || data.status === "submitted") return;
    const started = new Date(data.started_at).getTime();
    const tick = () => setElapsed(Math.round((Date.now() - started) / 1000));
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [data]);

  const submit = useMutation({
    mutationFn: () => api<{ attempt: ReadingAttempt; outcome: ActivityOutcome }>("/reading/submit", { json: { attempt_id: attemptId, answers, time_spent_seconds: Math.min(elapsed, 14400) } }),
    onSuccess: (res) => {
      queryClient.setQueryData(["reading-attempt", attemptId], res.attempt);
      setOutcome(res.outcome);
      celebrate(res.outcome);
      ["dashboard", "reading-history", "mistakes"].forEach((k) => queryClient.invalidateQueries({ queryKey: [k] }));
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
    onError: (err) => push({ tone: "error", title: "Couldn't submit your answers", description: errorMessage(err) }),
  });

  if (isLoading) return <PageSkeleton />;
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />;
  const submitted = data.status === "submitted";
  const remaining = data.time_limit_minutes * 60 - elapsed;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link href="/reading" className="text-sm text-muted-foreground hover:text-foreground">
            ← Reading
          </Link>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">{data.passage.title}</h1>
          <p className="text-sm text-muted-foreground">
            Level {data.difficulty} · {data.passage.word_count} words · {data.questions.length} questions
          </p>
        </div>
        {!submitted && (
          <Badge tone={remaining < 0 ? "danger" : remaining < 120 ? "warning" : "default"}>
            <Clock className="size-3.5" /> {remaining >= 0 ? `${formatDuration(remaining)} left` : `${formatDuration(-remaining)} over`}
          </Badge>
        )}
      </div>
      {data.notice && (
        <Notice tone="default" icon={<Info className="mt-0.5 size-4" />}>
          {data.notice}
        </Notice>
      )}
      {submitted && (
        <Card>
          <CardBody className="flex flex-wrap items-center gap-6">
            <BandValue band={data.band} size="lg" />
            <div>
              <p className="text-2xl font-semibold">
                {data.correct} / {data.total}
              </p>
              <p className="text-sm text-muted-foreground">{percent(data.accuracy)} correct at level {data.difficulty}</p>
            </div>
            <p className="text-xs text-muted-foreground">Band estimates for short practice sets are approximate indicators, not official scores.</p>
          </CardBody>
        </Card>
      )}
      <SIActions outcome={outcome} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="lg:sticky lg:top-20 lg:max-h-[calc(100vh-7rem)] lg:overflow-y-auto">
          <CardBody>
            <article className="space-y-4 text-[15px] leading-relaxed">
              {data.passage.paragraphs.map((p) => (
                <p key={p.label} className={cn("rounded-lg", evidence?.evidence_paragraph === p.label && "bg-success-soft/60 p-2")}>
                  <span className="mr-2 font-semibold text-primary">{p.label}</span>
                  {evidence ? withEvidence(p.text, evidence.evidence) : <SpotlightText text={p.text} words={data.spotlight} />}
                </p>
              ))}
            </article>
            {data.spotlight.length > 0 && !evidence && <p className="mt-4 text-xs text-muted-foreground">Highlighted: words from your vocabulary list.</p>}
          </CardBody>
        </Card>
        <div className="space-y-4">
          {data.passage.headings.length > 0 && !submitted && (
            <Card>
              <CardBody>
                <p className="text-sm font-semibold">List of headings</p>
                <ol className="mt-2 list-[lower-roman] space-y-1 pl-5 text-sm">{data.passage.headings.map((h) => <li key={h}>{h}</li>)}</ol>
              </CardBody>
            </Card>
          )}
          <Card>
            <CardBody>
              <QuestionForm
                questions={data.questions}
                answers={answers}
                onChange={(qid, v) => setAnswers((a) => ({ ...a, [qid]: v }))}
                results={submitted ? data.results : undefined}
                headings={data.passage.headings}
                onShowEvidence={setEvidence}
              />
            </CardBody>
          </Card>
          {!submitted && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                {Object.values(answers).filter((v) => v.trim()).length} of {data.questions.length} answered
              </p>
              <Button size="lg" onClick={() => submit.mutate()} loading={submit.isPending}>
                Submit answers
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
