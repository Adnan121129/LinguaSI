"use client";

import { Play } from "lucide-react";
import { useState } from "react";

import { Button, Card, CardBody, CardHeader, Field, Input, Select } from "@/components/ui";
import { QTYPE_LABELS } from "@/lib/constants";
import { cn } from "@/lib/utils";

export type SetupValues = { difficulty: number | null; topic: string; question_count: number; time_limit_minutes: number; question_types: string[]; extra: Record<string, string> };

/** Options for generating a reading or listening practice set. */
export function AttemptSetup({
  types,
  defaults,
  extraFields,
  onStart,
  starting,
  defaultCount,
  defaultMinutes,
}: {
  types: string[];
  defaults: { difficulty: number | null; types: string[] };
  extraFields?: { key: string; label: string; options: [string, string][] }[];
  onStart: (values: SetupValues) => void;
  starting: boolean;
  defaultCount: number;
  defaultMinutes: number;
}) {
  const [difficulty, setDifficulty] = useState<number | null>(defaults.difficulty);
  const [topic, setTopic] = useState("");
  const [count, setCount] = useState(defaultCount);
  const [minutes, setMinutes] = useState(defaultMinutes);
  const [selected, setSelected] = useState<string[]>(defaults.types);
  const [extra, setExtra] = useState<Record<string, string>>({});
  return (
    <Card>
      <CardHeader title="Start a practice set" description="Leave difficulty on adaptive and SI picks the level from your recent results." />
      <CardBody className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Difficulty" htmlFor="difficulty">
            <Select id="difficulty" value={difficulty ?? ""} onChange={(e) => setDifficulty(e.target.value ? Number(e.target.value) : null)}>
              <option value="">Adaptive (recommended)</option>
              {[1, 2, 3, 4, 5].map((d) => (
                <option key={d} value={d}>
                  Level {d}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Topic (optional)" htmlFor="topic">
            <Input id="topic" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. environment" maxLength={60} />
          </Field>
          <Field label="Questions" htmlFor="count">
            <Select id="count" value={count} onChange={(e) => setCount(Number(e.target.value))}>
              {[4, 6, 8, 10, 12].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Time limit" htmlFor="minutes">
            <Select id="minutes" value={minutes} onChange={(e) => setMinutes(Number(e.target.value))}>
              {[10, 15, 20, 30, 40].map((n) => (
                <option key={n} value={n}>
                  {n} minutes
                </option>
              ))}
            </Select>
          </Field>
          {extraFields?.map((f) => (
            <Field key={f.key} label={f.label} htmlFor={f.key}>
              <Select id={f.key} value={extra[f.key] ?? ""} onChange={(e) => setExtra((x) => ({ ...x, [f.key]: e.target.value }))}>
                {f.options.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </Field>
          ))}
        </div>
        <div className="space-y-2">
          <p className="text-sm font-medium">Question types (optional)</p>
          <div className="flex flex-wrap gap-2">
            {types.map((t) => {
              const on = selected.includes(t);
              return (
                <button
                  key={t}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setSelected(on ? selected.filter((x) => x !== t) : [...selected, t])}
                  className={cn("rounded-full border px-3 py-1 text-sm", on ? "border-primary bg-primary-soft text-primary" : "border-border text-muted-foreground hover:bg-muted")}
                >
                  {QTYPE_LABELS[t] ?? t}
                </button>
              );
            })}
          </div>
        </div>
        <Button onClick={() => onStart({ difficulty, topic, question_count: count, time_limit_minutes: minutes, question_types: selected, extra })} loading={starting}>
          <Play className="size-4" /> Start
        </Button>
      </CardBody>
    </Card>
  );
}
