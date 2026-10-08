"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock, Lightbulb, RotateCcw, Send } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { SIActions, useToast } from "@/components/providers/toast";
import { Badge, Button, Card, CardBody, CardHeader, ErrorState, Input, Notice, PageSkeleton, Textarea } from "@/components/ui";
import { EvaluationView } from "@/components/writing/evaluation-view";
import { TaskVisual } from "@/components/writing/task-visual";
import { api, errorMessage } from "@/lib/api";
import type { ActivityOutcome, Hint, Submission } from "@/lib/types";
import { formatDuration, taskTypeLabel, titleCase, wordCount } from "@/lib/utils";

function Editor({ submission, onEvaluated }: { submission: Submission; onEvaluated: (outcome: ActivityOutcome) => void }) {
  const queryClient = useQueryClient();
  const { push, celebrate } = useToast();
  const task = submission.task;
  const [content, setContent] = useState(submission.content);
  const [elapsed, setElapsed] = useState(submission.time_spent_seconds);
  const [savedAt, setSavedAt] = useState<string | null>(submission.autosaved_at);
  const [question, setQuestion] = useState("");
  const [hints, setHints] = useState<Hint | null>(null);
  const lastSaved = useRef(submission.content);
  const words = wordCount(content);
  const limitSeconds = task.time_limit_minutes * 60;
  const exam = submission.mode === "exam";

  useEffect(() => {
    const id = window.setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => window.clearInterval(id);
  }, []);

  const save = useMutation({
    mutationFn: (text: string) => api<{ saved_at: string; word_count: number }>(`/writing/submissions/${submission.id}`, { method: "PUT", json: { content: text, time_spent_seconds: elapsed } }),
    onSuccess: (res, text) => {
      lastSaved.current = text;
      setSavedAt(res.saved_at);
    },
  });

  // Autosave a few seconds after the learner stops typing.
  useEffect(() => {
    if (content === lastSaved.current) return;
    const id = window.setTimeout(() => save.mutate(content), 2500);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [content]);

  const hint = useMutation({
    mutationFn: () => api<Hint>(`/writing/submissions/${submission.id}/hint`, { json: { question: question || null, content } }),
    onSuccess: (h) => {
      setHints(h);
      setQuestion("");
    },
    onError: (err) => push({ tone: "error", title: "Hints are unavailable right now", description: errorMessage(err) }),
  });

  const evaluate = useMutation({
    mutationFn: () => api<{ submission: Submission; outcome: ActivityOutcome }>("/writing/evaluate", { json: { submission_id: submission.id, content, time_spent_seconds: elapsed } }),
    onSuccess: (res) => {
      onEvaluated(res.outcome);
      celebrate(res.outcome);
      queryClient.setQueryData(["submission", submission.id], res.submission);
      queryClient.invalidateQueries({ queryKey: ["writing-history"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["mistakes"] });
    },
    onError: () => queryClient.invalidateQueries({ queryKey: ["submission", submission.id] }),
  });

  const remaining = limitSeconds - elapsed;
  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <div className="space-y-4 lg:col-span-2">
        <Card>
          <CardHeader title={task.title} description={`${taskTypeLabel(task.task_type)} · ${titleCase(task.module)} · ${titleCase(task.category)}`} />
          <CardBody className="space-y-3">
            <p className="whitespace-pre-line text-sm leading-relaxed">{task.prompt}</p>
            {task.instructions && <p className="text-sm text-muted-foreground">{task.instructions}</p>}
          </CardBody>
        </Card>
        {task.visual && <TaskVisual visual={task.visual} />}
        {!exam && (
          <Card>
            <CardHeader icon={<Lightbulb className="size-4" />} title="SI Tutor" description="Hints and guiding questions — the tutor never writes your essay for you." />
            <CardBody className="space-y-3">
              <form
                className="flex gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  hint.mutate();
                }}
              >
                <Input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask about your draft (optional)" aria-label="Question for the tutor" maxLength={500} />
                <Button type="submit" variant="secondary" loading={hint.isPending}>
                  Hint
                </Button>
              </form>
              {hints && (
                <div className="space-y-3 text-sm">
                  {hints.observations.length > 0 && (
                    <div>
                      <p className="font-medium">What I notice</p>
                      <ul className="mt-1 list-inside list-disc space-y-1 text-muted-foreground">{hints.observations.map((o) => <li key={o}>{o}</li>)}</ul>
                    </div>
                  )}
                  <div>
                    <p className="font-medium">Hints</p>
                    <ul className="mt-1 list-inside list-disc space-y-1">{hints.hints.map((h) => <li key={h}>{h}</li>)}</ul>
                  </div>
                  {hints.guiding_questions.length > 0 && (
                    <div>
                      <p className="font-medium">Ask yourself</p>
                      <ul className="mt-1 list-inside list-disc space-y-1 text-muted-foreground">{hints.guiding_questions.map((q) => <li key={q}>{q}</li>)}</ul>
                    </div>
                  )}
                  {hints.structure_feedback && <p className="rounded-xl bg-muted p-3">{hints.structure_feedback}</p>}
                  {hints.vocabulary_direction.length > 0 && <p className="text-muted-foreground">Useful language: {hints.vocabulary_direction.join(" · ")}</p>}
                  {hints.encouragement && <p className="text-primary">{hints.encouragement}</p>}
                  <p className="text-xs text-muted-foreground">Hints used: {hints.hints_used}</p>
                </div>
              )}
            </CardBody>
          </Card>
        )}
      </div>

      <div className="space-y-4 lg:col-span-3">
        {submission.status === "evaluation_failed" && (
          <Notice tone="warning">
            AI analysis was temporarily unavailable last time. Your response is saved — submit again to analyse it.
          </Notice>
        )}
        {evaluate.error && <ErrorState title="Analysis didn't finish" error={evaluate.error} onRetry={() => evaluate.mutate()} />}
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2.5 text-sm">
            <span className={words >= task.min_words ? "font-medium text-success" : "text-muted-foreground"}>
              {words} / {task.min_words} words
            </span>
            <span className="flex items-center gap-3 text-muted-foreground">
              <span className="flex items-center gap-1" aria-live="off">
                <Clock className="size-3.5" aria-hidden />
                {exam ? (remaining >= 0 ? `${formatDuration(remaining)} left` : `${formatDuration(-remaining)} over time`) : formatDuration(elapsed)}
              </span>
              <span>{save.isPending ? "Saving…" : savedAt ? "Saved" : ""}</span>
            </span>
          </div>
          <Textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={20}
            className="min-h-[420px] rounded-none border-0 focus:ring-0"
            placeholder={task.task_type === "task1" ? "Summarise the main features and make comparisons…" : "Plan your position, then write your essay here…"}
            aria-label="Your response"
            spellCheck={!exam}
          />
        </Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground">{exam ? "Exam mode: no hints, browser spell-check off, timed like the real test." : "Tutor mode: ask for hints at any time."}</p>
          <Button onClick={() => evaluate.mutate()} loading={evaluate.isPending} disabled={words < 20} size="lg">
            {submission.status === "evaluation_failed" ? <RotateCcw className="size-4" /> : <Send className="size-4" />}
            {evaluate.isPending ? "Analysing your writing…" : "Submit for evaluation"}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function SubmissionPage() {
  const { id } = useParams<{ id: string }>();
  const submissionId = Number(id);
  const { data, error, isLoading, refetch } = useQuery({ queryKey: ["submission", submissionId], queryFn: () => api<Submission>(`/writing/submissions/${submissionId}`) });
  const [outcome, setOutcome] = useState<ActivityOutcome | null>(null);
  if (isLoading) return <PageSkeleton />;
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link href="/writing" className="text-sm text-muted-foreground hover:text-foreground">
            ← Writing
          </Link>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">{data.status === "evaluated" ? "Writing evaluation" : data.task.title}</h1>
        </div>
        {data.status === "evaluated" && (
          <Badge tone="success">
            <CheckCircle2 className="size-3.5" /> Evaluated
          </Badge>
        )}
      </div>
      {data.status === "evaluated" && data.evaluation ? (
        <>
          <SIActions outcome={outcome} />
          <EvaluationView submission={data} />
        </>
      ) : (
        <Editor key={data.id} submission={data} onEvaluated={setOutcome} />
      )}
    </div>
  );
}
