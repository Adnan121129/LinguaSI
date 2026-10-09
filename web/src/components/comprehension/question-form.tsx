"use client";

import { CheckCircle2, CircleX, Quote } from "lucide-react";

import { ChoiceList } from "@/components/choice-list";
import { Badge, Input, Select } from "@/components/ui";
import { QTYPE_LABELS } from "@/lib/constants";
import type { Question, QuestionResult } from "@/lib/types";

const TFNG = ["TRUE", "FALSE", "NOT GIVEN"];
const YNNG = ["YES", "NO", "NOT GIVEN"];

function optionsFor(q: Question, headings?: string[]): string[] | null {
  if (q.qtype === "true_false_not_given") return q.options?.length ? q.options : TFNG;
  if (q.qtype === "yes_no_not_given") return q.options?.length ? q.options : YNNG;
  if (q.qtype === "matching_headings") return q.options?.length ? q.options : headings ?? null;
  return q.options?.length ? q.options : null;
}

/** Questions for a reading or listening attempt: inputs before submission, marked results with evidence after. */
export function QuestionForm({
  questions,
  answers,
  onChange,
  results,
  headings,
  onShowEvidence,
}: {
  questions: Question[];
  answers: Record<string, string>;
  onChange: (id: number, value: string) => void;
  results?: QuestionResult[];
  headings?: string[];
  onShowEvidence?: (result: QuestionResult) => void;
}) {
  const byId = Object.fromEntries((results ?? []).map((r) => [r.question_id, r]));
  return (
    <ol className="space-y-5">
      {questions.map((q, index) => {
        const result = byId[q.id];
        const options = optionsFor(q, headings);
        return (
          <li key={q.id} className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-muted-foreground">{index + 1}.</span>
              <Badge>{QTYPE_LABELS[q.qtype] ?? q.qtype}</Badge>
              {q.word_limit && !result && <span className="text-xs text-muted-foreground">No more than {q.word_limit} word{q.word_limit > 1 ? "s" : ""}</span>}
              {result && (result.correct ? <CheckCircle2 className="size-4 text-success" aria-label="Correct" /> : <CircleX className="size-4 text-danger" aria-label="Incorrect" />)}
            </div>
            <p className="text-sm font-medium leading-relaxed">{q.prompt}</p>
            {result ? (
              <div className="space-y-1.5 rounded-xl bg-muted/60 p-3 text-sm">
                {!result.correct && (
                  <p>
                    <span className="text-muted-foreground">Your answer:</span> {result.your_answer || <em className="text-muted-foreground">no answer</em>}
                  </p>
                )}
                <p>
                  <span className="text-muted-foreground">Answer:</span> <span className="font-semibold text-success">{result.answer}</span>
                </p>
                {result.note && <p className="text-warning">{result.note}</p>}
                {result.explanation && <p className="text-muted-foreground">{result.explanation}</p>}
                {result.evidence && (
                  <button type="button" onClick={() => onShowEvidence?.(result)} className="flex items-start gap-1.5 text-left text-primary hover:underline">
                    <Quote className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                    <span>
                      “{result.evidence}”{result.evidence_paragraph ? ` (paragraph ${result.evidence_paragraph})` : ""}
                    </span>
                  </button>
                )}
              </div>
            ) : options && options.length > 6 ? (
              <Select value={answers[q.id] ?? ""} onChange={(e) => onChange(q.id, e.target.value)} aria-label={`Answer for question ${index + 1}`}>
                <option value="">Choose…</option>
                {options.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </Select>
            ) : options ? (
              <ChoiceList name={`q-${q.id}`} options={options} value={answers[q.id]} onChange={(v) => onChange(q.id, v)} />
            ) : (
              <Input value={answers[q.id] ?? ""} onChange={(e) => onChange(q.id, e.target.value)} placeholder="Your answer" aria-label={`Answer for question ${index + 1}`} autoComplete="off" />
            )}
          </li>
        );
      })}
    </ol>
  );
}

/** Highlights an evidence quote inside a block of text. */
export function withEvidence(text: string, evidence: string | null): React.ReactNode {
  // Quotes may end with "..." when the evidence was trimmed; match and highlight the quoted words only.
  const quote = evidence?.trim().replace(/[.…]+$/, "") ?? "";
  if (!quote) return text;
  const index = text.toLowerCase().indexOf(quote.toLowerCase().slice(0, 120));
  if (index < 0) return text;
  const length = Math.min(quote.length, text.length - index);
  return (
    <>
      {text.slice(0, index)}
      <mark className="mark-evidence text-foreground">{text.slice(index, index + length)}</mark>
      {text.slice(index + length)}
    </>
  );
}
