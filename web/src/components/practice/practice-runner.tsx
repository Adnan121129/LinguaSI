"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleX, RotateCcw, Shuffle, Trophy } from "lucide-react";
import Link from "next/link";
import { useMemo, useRef, useState } from "react";

import { ChoiceList } from "@/components/choice-list";
import { SIActions, useToast } from "@/components/providers/toast";
import { Badge, Button, Card, CardBody, ErrorState, Input, Notice, ProgressBar, Textarea, buttonClasses } from "@/components/ui";
import { QTYPE_LABELS } from "@/lib/constants";
import { api } from "@/lib/api";
import type { PracticeItem, PracticeSet, PracticeSubmitResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

function WordOrder({ prompt, value, onChange }: { prompt: string; value: string; onChange: (v: string) => void }) {
  const tokens = useMemo(() => (prompt.split(": ").slice(1).join(": ") || prompt).split(" / ").map((t) => t.trim()).filter(Boolean), [prompt]);
  const [picked, setPicked] = useState<number[]>([]);
  const toggle = (index: number) => {
    const next = picked.includes(index) ? picked.filter((i) => i !== index) : [...picked, index];
    setPicked(next);
    onChange(next.map((i) => tokens[i]).join(" "));
  };
  return (
    <div className="space-y-3">
      <div className="min-h-12 rounded-xl border border-dashed border-border p-3 text-sm" aria-live="polite">
        {value || <span className="text-muted-foreground">Tap the words in the right order…</span>}
      </div>
      <div className="flex flex-wrap gap-2">
        {tokens.map((token, i) => (
          <button
            key={`${token}-${i}`}
            type="button"
            onClick={() => toggle(i)}
            aria-pressed={picked.includes(i)}
            className={cn("rounded-lg border px-3 py-1.5 text-sm transition", picked.includes(i) ? "border-primary bg-primary-soft text-primary opacity-60" : "border-border bg-card hover:bg-muted")}
          >
            {token}
          </button>
        ))}
        {picked.length > 0 && (
          <button
            type="button"
            onClick={() => {
              setPicked([]);
              onChange("");
            }}
            className="inline-flex items-center gap-1 rounded-lg px-2 py-1.5 text-sm text-muted-foreground hover:bg-muted"
          >
            <RotateCcw className="size-3.5" aria-hidden /> Clear
          </button>
        )}
      </div>
    </div>
  );
}

function ItemInput({ item, value, onChange }: { item: PracticeItem; value: string; onChange: (v: string) => void }) {
  if (item.qtype === "multiple_choice" && item.options) return <ChoiceList name={item.id} options={item.options} value={value} onChange={onChange} />;
  if (item.qtype === "sentence_order") return <WordOrder prompt={item.prompt} value={value} onChange={onChange} />;
  if (item.qtype === "gap_fill") return <Input value={value} onChange={(e) => onChange(e.target.value)} placeholder="Type the missing word(s)" aria-label="Your answer" />;
  return <Textarea rows={2} value={value} onChange={(e) => onChange(e.target.value)} placeholder="Write the corrected sentence" aria-label="Your answer" />;
}

/** Runs any practice set (grammar drill, mistake repair challenge, revision session, Lab practice). */
export function PracticeRunner({ practice, onComplete }: { practice: PracticeSet; onComplete?: (result: PracticeSubmitResponse) => void }) {
  const queryClient = useQueryClient();
  const { celebrate } = useToast();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const started = useRef(Date.now());
  const [result, setResult] = useState<PracticeSubmitResponse | null>(null);
  const submit = useMutation({
    mutationFn: () => api<PracticeSubmitResponse>(`/practice/sets/${practice.id}/submit`, { json: { answers, duration_seconds: Math.round((Date.now() - started.current) / 1000) } }),
    onSuccess: (res) => {
      setResult(res);
      celebrate(res.outcome);
      queryClient.setQueryData(["practice", practice.id], res.practice);
      ["dashboard", "mistakes", "mistake-summary", "practice-list"].forEach((key) => queryClient.invalidateQueries({ queryKey: [key] }));
      onComplete?.(res);
    },
  });

  const done = result?.practice ?? (practice.status === "completed" ? practice : null);
  if (done) {
    const byId = Object.fromEntries(done.results.map((r) => [r.id, r]));
    return (
      <div className="space-y-6">
        <Card>
          <CardBody className="flex flex-wrap items-center gap-6">
            <div className="grid size-16 place-items-center rounded-2xl bg-primary-soft text-primary">
              <Trophy className="size-7" aria-hidden />
            </div>
            <div className="flex-1">
              <p className="text-3xl font-semibold">
                {done.score} / {done.total}
              </p>
              <p className="text-sm text-muted-foreground">{Math.round(done.accuracy ?? 0)}% correct</p>
              <ProgressBar className="mt-2 max-w-sm" value={done.accuracy ?? 0} tone={(done.accuracy ?? 0) >= 80 ? "success" : "primary"} label="Accuracy" />
            </div>
            {result && result.mastered_mistakes.length > 0 && <Badge tone="success">{result.mastered_mistakes.length} mistake(s) mastered</Badge>}
          </CardBody>
        </Card>
        <SIActions outcome={result?.outcome} />
        <ol className="space-y-3">
          {done.items.map((item, index) => {
            const r = byId[item.id];
            return (
              <li key={item.id}>
                <Card className={cn(r?.correct ? "border-success/30" : "border-danger/30")}>
                  <CardBody className="space-y-2">
                    <div className="flex items-start gap-2">
                      {r?.correct ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" aria-label="Correct" /> : <CircleX className="mt-0.5 size-4 shrink-0 text-danger" aria-label="Incorrect" />}
                      <p className="font-medium">
                        {index + 1}. {item.prompt}
                      </p>
                    </div>
                    {r && (
                      <div className="space-y-1 pl-6 text-sm">
                        {!r.correct && (
                          <p>
                            <span className="text-muted-foreground">Your answer:</span> {r.your_answer || <em className="text-muted-foreground">no answer</em>}
                          </p>
                        )}
                        <p>
                          <span className="text-muted-foreground">Answer:</span> <span className="font-medium text-success">{r.answer}</span>
                        </p>
                        {r.explanation && <p className="text-muted-foreground">{r.explanation}</p>}
                      </div>
                    )}
                  </CardBody>
                </Card>
              </li>
            );
          })}
        </ol>
        <div className="flex flex-wrap gap-3">
          <Link href="/mistakes" className={buttonClasses("outline")}>
            Back to My Mistakes
          </Link>
          <Link href="/dashboard" className={buttonClasses("primary")}>
            Dashboard
          </Link>
        </div>
      </div>
    );
  }

  const answered = practice.items.filter((i) => (answers[i.id] ?? "").trim()).length;
  return (
    <div className="space-y-6">
      <Notice tone="primary" icon={<Shuffle className="mt-0.5 size-4 text-primary" aria-hidden />}>
        {practice.why}
      </Notice>
      <ol className="space-y-4">
        {practice.items.map((item, index) => (
          <li key={item.id}>
            <Card>
              <CardBody className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge>{QTYPE_LABELS[item.qtype] ?? item.qtype}</Badge>
                  {item.source === "personal" && <Badge tone="warning">From your own work</Badge>}
                </div>
                <p className="font-medium">
                  {index + 1}. {item.qtype === "sentence_order" ? "Put the words in the correct order." : item.prompt}
                </p>
                <ItemInput item={item} value={answers[item.id] ?? ""} onChange={(v) => setAnswers((a) => ({ ...a, [item.id]: v }))} />
              </CardBody>
            </Card>
          </li>
        ))}
      </ol>
      {submit.error && <ErrorState error={submit.error} onRetry={() => submit.mutate()} />}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          {answered} of {practice.items.length} answered
        </p>
        <Button size="lg" onClick={() => submit.mutate()} loading={submit.isPending}>
          Check my answers
        </Button>
      </div>
    </div>
  );
}
