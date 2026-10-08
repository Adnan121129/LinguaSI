"use client";

import { ArrowDownRight, ArrowRight, ArrowUpRight, Info } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { BandValue, CriterionBar } from "@/components/band";
import { Badge, Card, CardBody, CardHeader, buttonClasses } from "@/components/ui";
import type { Submission, WritingErrorItem } from "@/lib/types";
import { formatBand, taskTypeLabel, titleCase } from "@/lib/utils";

import { HighlightedEssay } from "./highlighted-essay";

function List({ title, items, tone = "default" }: { title: string; items: string[]; tone?: "default" | "success" | "warning" }) {
  if (!items.length) return null;
  const dot = tone === "success" ? "bg-success" : tone === "warning" ? "bg-warning" : "bg-primary";
  return (
    <div>
      <p className="text-sm font-semibold">{title}</p>
      <ul className="mt-2 space-y-1.5 text-sm">
        {items.map((item) => (
          <li key={item} className="flex gap-2">
            <span className={`mt-2 size-1.5 shrink-0 rounded-full ${dot}`} aria-hidden />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function EvaluationView({ submission }: { submission: Submission }) {
  const evaluation = submission.evaluation!;
  const [active, setActive] = useState<WritingErrorItem | null>(evaluation.errors[0] ?? null);
  const previous = submission.previous;
  const metrics = evaluation.metrics as Record<string, number | string | boolean | null>;

  return (
    <div className="space-y-6">
      <Card>
        <CardBody className="flex flex-wrap items-center gap-6">
          <BandValue band={evaluation.overall_band} size="xl" label={evaluation.label} />
          <div className="min-w-0 flex-1 space-y-2">
            <p className="text-sm">{evaluation.summary}</p>
            <div className="flex flex-wrap gap-2">
              <Badge>{submission.word_count} words</Badge>
              <Badge>{taskTypeLabel(submission.task.task_type)}</Badge>
              <Badge tone={submission.mode === "exam" ? "accent" : "primary"}>{submission.mode === "exam" ? "Exam mode" : "Tutor mode"}</Badge>
              {evaluation.is_mock && <Badge tone="warning">Mock AI Mode analysis</Badge>}
            </div>
          </div>
          {previous && (
            <div className="rounded-xl bg-muted p-3 text-sm">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Compared with your {previous.same_task ? "previous attempt" : "last essay"}</p>
              <p className="mt-1 flex items-center gap-1 font-semibold">
                {formatBand(previous.overall_band)} → {formatBand(evaluation.overall_band)}
                {evaluation.overall_band > previous.overall_band ? (
                  <ArrowUpRight className="size-4 text-success" aria-label="higher" />
                ) : evaluation.overall_band < previous.overall_band ? (
                  <ArrowDownRight className="size-4 text-danger" aria-label="lower" />
                ) : null}
              </p>
            </div>
          )}
        </CardBody>
        <p className="border-t border-border px-5 py-3 text-xs text-muted-foreground">{evaluation.disclaimer}</p>
      </Card>

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader
            title="Your response"
            description={
              evaluation.errors.length
                ? `${evaluation.errors.length} issue${evaluation.errors.length === 1 ? "" : "s"} highlighted — select one to see the correction.`
                : "No language errors were detected in this response."
            }
          />
          <CardBody>
            <HighlightedEssay text={submission.content} errors={evaluation.errors} activeId={active?.id} onSelect={setActive} />
          </CardBody>
        </Card>
        <div className="space-y-6 lg:col-span-2">
          {active && (
            <Card className="border-primary/30">
              <CardBody className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <Badge tone={active.severity === "high" ? "danger" : active.severity === "medium" ? "warning" : "default"}>{titleCase(active.subcategory)}</Badge>
                  {active.repeated && <Badge tone="danger">Repeated mistake</Badge>}
                </div>
                <p className="text-sm">
                  <span className="mark-error">{active.original}</span> → <span className="font-semibold text-success">{active.corrected}</span>
                </p>
                <p className="text-sm text-muted-foreground">{active.explanation}</p>
                {active.mistake_id && (
                  <Link href={`/mistakes?focus=${active.mistake_id}`} className="inline-flex items-center gap-1 text-sm font-medium text-primary">
                    Saved to My Mistakes <ArrowRight className="size-3.5" />
                  </Link>
                )}
              </CardBody>
            </Card>
          )}
          <Card>
            <CardHeader title="Criteria" description="Each IELTS-style criterion is estimated separately." />
            <CardBody className="space-y-4">
              {evaluation.criteria.map((c) => (
                <CriterionBar key={c.key} label={c.label} band={c.band} comment={c.comment} />
              ))}
            </CardBody>
          </Card>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardBody className="space-y-5">
            <List title="Strengths" items={evaluation.strengths} tone="success" />
            <List title="To improve" items={evaluation.weaknesses} tone="warning" />
          </CardBody>
        </Card>
        {evaluation.task_response_issues.length + evaluation.cohesion_issues.length + evaluation.vocabulary_issues.length > 0 && (
          <Card>
            <CardBody className="space-y-5">
              <List title="Task response" items={evaluation.task_response_issues} />
              <List title="Coherence & cohesion" items={evaluation.cohesion_issues} />
              <List title="Vocabulary" items={evaluation.vocabulary_issues} />
            </CardBody>
          </Card>
        )}
      </div>

      <Card>
        <CardHeader title="Your next steps" />
        <CardBody className="space-y-4">
          <List title="Advice" items={evaluation.advice} />
          {evaluation.recommended_exercise?.focus && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-primary-soft/60 p-4">
              <div>
                <p className="font-semibold">{evaluation.recommended_exercise.title}</p>
                <p className="text-sm text-muted-foreground">{evaluation.recommended_exercise.description}</p>
              </div>
              <Link href={`/practice/new?focus=${evaluation.recommended_exercise.focus}`} className={buttonClasses("primary", "sm")}>
                Practise now
              </Link>
            </div>
          )}
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            {[
              ["Paragraphs", metrics.paragraph_count],
              ["Avg. sentence", metrics.avg_sentence_length ? `${metrics.avg_sentence_length} words` : null],
              ["Lexical diversity", metrics.lexical_diversity],
              ["Linking words", metrics.linker_variety],
            ].map(([label, value]) => (
              <div key={String(label)} className="rounded-xl bg-muted p-3">
                <dt className="text-xs text-muted-foreground">{label}</dt>
                <dd className="font-semibold">{value === null || value === undefined ? "—" : String(value)}</dd>
              </div>
            ))}
          </dl>
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Info className="size-3.5" aria-hidden /> Evaluated by {evaluation.is_mock ? "LinguaSI's built-in analysis (Mock AI Mode)" : `${evaluation.provider} · ${evaluation.model}`}
          </p>
        </CardBody>
      </Card>
    </div>
  );
}
