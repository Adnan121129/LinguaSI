"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, CircleX, Lightbulb, MessageCircleQuestion, SkipForward, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ChoiceList } from "@/components/choice-list";
import { SIActions, useToast } from "@/components/providers/toast";
import { Badge, Button, Card, CardBody, EmptyState, Input, Notice, ProgressBar, Textarea } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { ActivityOutcome, ReviewResult, VocabExercise, VocabToday } from "@/lib/types";
import { formatDate, titleCase } from "@/lib/utils";

type Explanation = { explanation: string; examples: string[]; common_mistake: string; usage_tip: string; is_mock: boolean };

const TYPE_LABELS: Record<string, string> = {
  multiple_choice: "Choose the word",
  synonym: "Synonym",
  antonym: "Opposite",
  fill_blank: "Fill the gap",
  sentence_completion: "Complete the sentence",
  collocation: "Collocation",
  word_formation: "Word formation",
  contextual: "Meaning in context",
  definition: "Definition",
  use_in_sentence: "Use it in a sentence",
};

export function ReviewSession({ session, onFinished }: { session: VocabToday; onFinished?: () => void }) {
  const queryClient = useQueryClient();
  const { push, celebrate } = useToast();
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [score, setScore] = useState({ correct: 0, total: 0, xp: 0 });
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [summary, setSummary] = useState<{ reviews: number; correct: number; accuracy: number | null; outcome: ActivityOutcome | null } | null>(null);
  const shownAt = useRef(0);
  const exercise: VocabExercise | undefined = session.exercises[index];

  useEffect(() => {
    shownAt.current = Date.now();
  }, [index]);

  const review = useMutation({
    mutationFn: () => api<ReviewResult>("/vocabulary/review", { json: { exercise_id: exercise!.id, answer, response_ms: Date.now() - shownAt.current, hinted: false } }),
    onSuccess: (res) => {
      setResult(res);
      setScore((s) => ({ correct: s.correct + (res.correct ? 1 : 0), total: s.total + 1, xp: s.xp + res.xp_gained }));
    },
    onError: (err) => push({ tone: "error", title: "Couldn't check that answer", description: errorMessage(err) }),
  });
  const known = useMutation({
    mutationFn: () => api(`/vocabulary/words/${exercise!.user_vocab_id}/known`, { method: "POST" }),
    onSuccess: () => next(),
  });
  const explain = useMutation({
    mutationFn: (itemId: number) => api<Explanation>(`/vocabulary/items/${itemId}/explain`, { method: "POST" }),
    onSuccess: setExplanation,
    onError: (err) => push({ tone: "warning", title: "Explanation unavailable", description: errorMessage(err) }),
  });
  const complete = useMutation({
    mutationFn: () => api<typeof summary>("/vocabulary/session/complete", { json: { started_at: session.started_at, duration_seconds: 0 } }),
    onSuccess: (res) => {
      setSummary(res);
      celebrate(res?.outcome);
      ["dashboard", "vocab-insights", "vocab-words", "mistakes"].forEach((key) => queryClient.invalidateQueries({ queryKey: [key] }));
    },
  });

  function next() {
    setResult(null);
    setAnswer("");
    setExplanation(null);
    if (index + 1 >= session.exercises.length) complete.mutate();
    else setIndex((i) => i + 1);
  }

  if (!session.exercises.length) {
    return <EmptyState icon={<CheckCircle2 className="size-5" />} title="You're all caught up" description="No words are due right now. New words are added each day — come back tomorrow, or add words from the word bank." />;
  }

  if (summary || complete.isPending) {
    return (
      <Card>
        <CardBody className="space-y-4">
          <p className="text-2xl font-semibold">Session complete</p>
          {summary ? (
            <>
              <p className="text-muted-foreground">
                {summary.correct} of {summary.reviews} correct ({Math.round(summary.accuracy ?? 0)}%) · +{score.xp} XP from answers
              </p>
              <ProgressBar value={summary.accuracy ?? 0} tone="success" label="Session accuracy" />
              <SIActions outcome={summary.outcome} />
              <Button
                onClick={() => {
                  queryClient.invalidateQueries({ queryKey: ["vocab-today"] });
                  onFinished?.();
                }}
              >
                Check for more words
              </Button>
            </>
          ) : (
            <p className="text-muted-foreground">Saving your session…</p>
          )}
        </CardBody>
      </Card>
    );
  }

  const ex = exercise!;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <ProgressBar value={(index / session.exercises.length) * 100} label="Session progress" />
        <span className="shrink-0 text-sm text-muted-foreground">
          {index + 1} / {session.exercises.length}
        </span>
      </div>
      <Card>
        <CardBody className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="primary">{TYPE_LABELS[ex.type] ?? titleCase(ex.type)}</Badge>
            {ex.is_new ? <Badge tone="accent">New word</Badge> : <Badge>{titleCase(ex.state)}</Badge>}
            {ex.reason_detail && <span className="text-xs text-muted-foreground">Why this word: {ex.reason_detail}</span>}
          </div>
          {ex.word && <p className="text-2xl font-semibold">{ex.word}</p>}
          <p className="text-lg">{ex.prompt}</p>
          {ex.hint && !result && (
            <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <Lightbulb className="size-4" aria-hidden /> {ex.hint}
            </p>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!result && answer.trim()) review.mutate();
            }}
            className="space-y-3"
          >
            {ex.input === "choice" && ex.options ? (
              <ChoiceList name={ex.id} options={ex.options} value={answer} onChange={setAnswer} disabled={!!result} correct={result ? result.correct_answer : undefined} />
            ) : ex.input === "sentence" ? (
              <Textarea rows={3} value={answer} onChange={(e) => setAnswer(e.target.value)} disabled={!!result} placeholder="Write your own sentence…" aria-label="Your sentence" />
            ) : (
              <Input value={answer} onChange={(e) => setAnswer(e.target.value)} disabled={!!result} placeholder="Type your answer" aria-label="Your answer" autoComplete="off" />
            )}
            {!result && (
              <div className="flex flex-wrap gap-2">
                <Button type="submit" disabled={!answer.trim()} loading={review.isPending}>
                  Check
                </Button>
                <Button type="button" variant="ghost" onClick={() => known.mutate()} loading={known.isPending}>
                  <SkipForward className="size-4" /> I already know this
                </Button>
              </div>
            )}
          </form>
        </CardBody>
      </Card>

      {result && (
        <Card className={result.correct ? "border-success/40" : "border-danger/40"}>
          <CardBody className="space-y-3">
            <p className={`flex items-center gap-2 font-semibold ${result.correct ? "text-success" : "text-danger"}`}>
              {result.correct ? <CheckCircle2 className="size-5" /> : <CircleX className="size-5" />}
              {result.correct ? "Correct!" : `The answer is: ${result.correct_answer}`}
            </p>
            {result.feedback && <p className="text-sm">{result.feedback}</p>}
            <div className="rounded-xl bg-muted p-3 text-sm">
              <p>
                <span className="font-semibold">{result.item.word}</span> <span className="text-muted-foreground">({result.item.part_of_speech})</span> — {result.item.definition}
              </p>
              <p className="mt-1 italic text-muted-foreground">{result.item.example}</p>
              {result.item.collocations.length > 0 && <p className="mt-1 text-muted-foreground">Collocations: {result.item.collocations.slice(0, 3).join(" · ")}</p>}
            </div>
            <p className="text-xs text-muted-foreground">
              {titleCase(result.state_before)} → <span className="font-medium text-foreground">{titleCase(result.state_after)}</span> · next review {formatDate(result.next_review_at, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
            </p>
            {explanation && (
              <Notice tone="primary" icon={<Sparkles className="mt-0.5 size-4 text-primary" />}>
                <p>{explanation.explanation}</p>
                {explanation.examples.length > 0 && <ul className="mt-1 list-inside list-disc">{explanation.examples.map((e) => <li key={e}>{e}</li>)}</ul>}
                {explanation.common_mistake && <p className="mt-1">Common mistake: {explanation.common_mistake}</p>}
                {explanation.usage_tip && <p className="mt-1">Tip: {explanation.usage_tip}</p>}
              </Notice>
            )}
            <div className="flex flex-wrap gap-2">
              <Button onClick={next}>
                {index + 1 >= session.exercises.length ? "Finish session" : "Next word"} <ArrowRight className="size-4" />
              </Button>
              {!explanation && (
                <Button variant="ghost" onClick={() => explain.mutate(result.item.id)} loading={explain.isPending}>
                  <MessageCircleQuestion className="size-4" /> Explain this word
                </Button>
              )}
            </div>
          </CardBody>
        </Card>
      )}
      <p className="text-xs text-muted-foreground">
        {score.correct}/{score.total} correct so far · +{score.xp} XP
      </p>
    </div>
  );
}
