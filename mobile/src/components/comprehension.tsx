import { router } from "expo-router";
import { CheckCircle2, CircleX, Play, Quote } from "lucide-react-native";
import { useState, type ReactNode } from "react";
import { Pressable, ScrollView, View } from "react-native";

import { BandValue } from "@/components/band";
import { Badge, Button, Card, Chip, ChoiceList, Input, ListRow, Row, Text } from "@/components/ui";
import { QTYPE_LABELS } from "@/lib/constants";
import { useTheme } from "@/lib/theme";
import type { AttemptSummary, Question, QuestionResult } from "@/lib/types";
import { formatDate, percent } from "@/lib/utils";

export const READING_TYPES = ["multiple_choice", "true_false_not_given", "yes_no_not_given", "matching_headings", "matching_information", "sentence_completion", "summary_completion", "short_answer"];
export const LISTENING_TYPES = ["multiple_choice", "form_completion", "note_completion", "sentence_completion", "short_answer"];

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
      <Text variant="subheading">Start a practice set</Text>
      <Text variant="caption" tone="muted">Leave difficulty on adaptive and SI picks the level from your recent results.</Text>
      <Text variant="small" weight="600">Difficulty</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
        <Chip label="Adaptive" selected={difficulty === null} onPress={() => setDifficulty(null)} />
        {[1, 2, 3, 4, 5].map((d) => (
          <Chip key={d} label={`Level ${d}`} selected={difficulty === d} onPress={() => setDifficulty(d)} />
        ))}
      </ScrollView>
      <Input label="Topic (optional)" value={topic} onChangeText={setTopic} placeholder="e.g. environment" maxLength={60} />
      <Text variant="small" weight="600">Questions</Text>
      <Row wrap>
        {[4, 6, 8, 10, 12].map((n) => (
          <Chip key={n} label={String(n)} selected={count === n} onPress={() => setCount(n)} />
        ))}
      </Row>
      <Text variant="small" weight="600">Time limit</Text>
      <Row wrap>
        {[10, 15, 20, 30, 40].map((n) => (
          <Chip key={n} label={`${n} min`} selected={minutes === n} onPress={() => setMinutes(n)} />
        ))}
      </Row>
      {extraFields?.map((f) => (
        <View key={f.key} style={{ gap: 8 }}>
          <Text variant="small" weight="600">{f.label}</Text>
          <Row wrap>
            {f.options.map(([value, label]) => (
              <Chip key={value || "any"} label={label} selected={(extra[f.key] ?? "") === value} onPress={() => setExtra((x) => ({ ...x, [f.key]: value }))} />
            ))}
          </Row>
        </View>
      ))}
      <Text variant="small" weight="600">Question types (optional)</Text>
      <Row wrap>
        {types.map((t) => {
          const on = selected.includes(t);
          return <Chip key={t} label={QTYPE_LABELS[t] ?? t} selected={on} onPress={() => setSelected(on ? selected.filter((x) => x !== t) : [...selected, t])} />;
        })}
      </Row>
      <Button title="Start" icon={Play} loading={starting} onPress={() => onStart({ difficulty, topic, question_count: count, time_limit_minutes: minutes, question_types: selected, extra })} />
    </Card>
  );
}

export function AttemptHistory({ items, base }: { items: AttemptSummary[]; base: "/reading" | "/listening" }) {
  return (
    <>
      {items.map((a) => (
        <ListRow
          key={a.id}
          title={a.title}
          subtitle={`Level ${a.difficulty} · ${a.status === "submitted" ? `${a.correct}/${a.total} correct (${percent(a.accuracy)})` : "In progress"} · ${formatDate(a.submitted_at ?? a.started_at)}`}
          right={a.band !== null ? <BandValue band={a.band} size="sm" label={null} /> : <Badge tone="primary" label="Continue" />}
          onPress={() => router.push(`${base}/${a.id}`)}
        />
      ))}
    </>
  );
}

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
  const { colors } = useTheme();
  const byId = Object.fromEntries((results ?? []).map((r) => [r.question_id, r]));
  return (
    <View style={{ gap: 18 }}>
      {questions.map((q, index) => {
        const result = byId[q.id];
        const options = optionsFor(q, headings);
        return (
          <View key={q.id} style={{ gap: 8 }}>
            <Row wrap gap={6}>
              <Text variant="small" weight="700" tone="muted">{index + 1}.</Text>
              <Badge label={QTYPE_LABELS[q.qtype] ?? q.qtype} />
              {q.word_limit && !result ? <Text variant="caption" tone="muted">No more than {q.word_limit} word{q.word_limit > 1 ? "s" : ""}</Text> : null}
              {result ? result.correct ? <CheckCircle2 size={16} color={colors.success} accessibilityLabel="Correct" /> : <CircleX size={16} color={colors.danger} accessibilityLabel="Incorrect" /> : null}
            </Row>
            <Text weight="600">{q.prompt}</Text>
            {result ? (
              <View style={{ backgroundColor: colors.muted, borderRadius: 12, padding: 12, gap: 6 }}>
                {!result.correct ? (
                  <Text variant="small">
                    <Text variant="small" tone="muted">Your answer: </Text>
                    {result.your_answer || "no answer"}
                  </Text>
                ) : null}
                <Text variant="small">
                  <Text variant="small" tone="muted">Answer: </Text>
                  <Text variant="small" tone="success" weight="700">{result.answer}</Text>
                </Text>
                {result.note ? <Text variant="small" tone="warning">{result.note}</Text> : null}
                {result.explanation ? <Text variant="small" tone="muted">{result.explanation}</Text> : null}
                {result.evidence ? (
                  <Pressable onPress={() => onShowEvidence?.(result)} accessibilityRole="button" style={{ flexDirection: "row", gap: 6, alignItems: "flex-start" }}>
                    <Quote size={14} color={colors.primary} style={{ marginTop: 2 }} />
                    <Text variant="small" tone="primary" style={{ flex: 1 }}>
                      “{result.evidence}”{result.evidence_paragraph ? ` (paragraph ${result.evidence_paragraph})` : ""}
                    </Text>
                  </Pressable>
                ) : null}
              </View>
            ) : options ? (
              <ChoiceList options={options} value={answers[q.id]} onChange={(v) => onChange(q.id, v)} />
            ) : (
              <Input value={answers[q.id] ?? ""} onChangeText={(v) => onChange(q.id, v)} placeholder="Your answer" accessibilityLabel={`Answer for question ${index + 1}`} autoCapitalize="none" autoCorrect={false} />
            )}
          </View>
        );
      })}
    </View>
  );
}

/** Highlights an evidence quote inside a block of text (quotes may end with "..." when trimmed). */
export function withEvidence(text: string, evidence: string | null, highlight: string): ReactNode {
  const quote = evidence?.trim().replace(/[.…]+$/, "") ?? "";
  if (!quote) return text;
  const index = text.toLowerCase().indexOf(quote.toLowerCase().slice(0, 120));
  if (index < 0) return text;
  const length = Math.min(quote.length, text.length - index);
  return (
    <>
      {text.slice(0, index)}
      <Text style={{ backgroundColor: highlight }}>{text.slice(index, index + length)}</Text>
      {text.slice(index + length)}
    </>
  );
}

/** Words from the learner's vocabulary list, highlighted where they appear in a passage. */
export function spotlight(text: string, words: string[], color: { fg: string; bg: string }): ReactNode {
  if (!words.length) return text;
  const pattern = new RegExp(`\\b(${words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})\\b`, "gi");
  return text.split(pattern).map((part, i) =>
    i % 2 === 1 ? (
      <Text key={i} style={{ color: color.fg, backgroundColor: color.bg }}>
        {part}
      </Text>
    ) : (
      part
    ),
  );
}
