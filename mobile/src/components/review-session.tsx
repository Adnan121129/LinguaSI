import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, CircleX, Lightbulb, MessageCircleQuestion, SkipForward, Sparkles } from "lucide-react-native";
import { useEffect, useRef, useState } from "react";
import { View } from "react-native";

import { SIActions, useToast } from "@/components/toast";
import { Badge, Button, Card, ChoiceList, EmptyState, Input, Notice, ProgressBar, Row, Text } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import type { ActivityOutcome, ReviewResult, VocabExercise, VocabToday } from "@/lib/types";
import { formatDateTime, titleCase } from "@/lib/utils";

type Explanation = { explanation: string; examples: string[]; common_mistake: string; usage_tip: string; is_mock: boolean };
type Summary = { reviews: number; correct: number; accuracy: number | null; outcome: ActivityOutcome | null };

export const EXERCISE_LABELS: Record<string, string> = {
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

/** One spaced-repetition session: answer, see feedback and the word's next review, then a summary. */
export function ReviewSession({ session, onFinished }: { session: VocabToday; onFinished?: () => void }) {
  const queryClient = useQueryClient();
  const { colors } = useTheme();
  const { push, celebrate } = useToast();
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [score, setScore] = useState({ correct: 0, total: 0, xp: 0 });
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
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
    onError: (err) => push({ tone: "error", title: "Couldn't update the word", description: errorMessage(err) }),
  });
  const explain = useMutation({
    mutationFn: (itemId: number) => api<Explanation>(`/vocabulary/items/${itemId}/explain`, { method: "POST" }),
    onSuccess: setExplanation,
    onError: (err) => push({ tone: "warning", title: "Explanation unavailable", description: errorMessage(err) }),
  });
  const complete = useMutation({
    mutationFn: () => api<Summary>("/vocabulary/session/complete", { json: { started_at: session.started_at, duration_seconds: 0 } }),
    onSuccess: (res) => {
      setSummary(res);
      celebrate(res.outcome);
      ["dashboard", "vocab-today", "vocab-insights", "vocab-words", "mistakes"].forEach((key) => queryClient.invalidateQueries({ queryKey: [key] }));
    },
    onError: (err) => push({ tone: "error", title: "Couldn't save the session", description: errorMessage(err) }),
  });

  function next() {
    setResult(null);
    setAnswer("");
    setExplanation(null);
    if (index + 1 >= session.exercises.length) complete.mutate();
    else setIndex((i) => i + 1);
  }

  if (!session.exercises.length) {
    return <EmptyState icon={CheckCircle2} title="You're all caught up" description="No words are due right now. New words are added each day — come back tomorrow, or add words from the word bank." />;
  }

  if (summary || complete.isPending || complete.isError) {
    return (
      <Card>
        <Text variant="title">Session complete</Text>
        {summary ? (
          <>
            <Text tone="muted">
              {summary.correct} of {summary.reviews} correct ({Math.round(summary.accuracy ?? 0)}%) · +{score.xp} XP from answers
            </Text>
            <ProgressBar value={summary.accuracy ?? 0} tone="success" label="Session accuracy" />
            <SIActions outcome={summary.outcome} />
            <Button title="Check for more words" onPress={onFinished} />
          </>
        ) : complete.isError ? (
          <Button title="Save the session again" onPress={() => complete.mutate()} />
        ) : (
          <Text tone="muted">Saving your session…</Text>
        )}
      </Card>
    );
  }

  const ex = exercise!;
  return (
    <View style={{ gap: 14 }}>
      <Row>
        <View style={{ flex: 1 }}>
          <ProgressBar value={(index / session.exercises.length) * 100} label="Session progress" />
        </View>
        <Text variant="small" tone="muted">
          {index + 1} / {session.exercises.length}
        </Text>
      </Row>
      <Card>
        <Row wrap>
          <Badge tone="primary" label={EXERCISE_LABELS[ex.type] ?? titleCase(ex.type)} />
          {ex.is_new ? <Badge tone="accent" label="New word" /> : <Badge label={titleCase(ex.state)} />}
        </Row>
        {ex.reason_detail ? <Text variant="caption" tone="muted">Why this word: {ex.reason_detail}</Text> : null}
        {ex.word ? <Text variant="title">{ex.word}</Text> : null}
        <Text variant="subheading" weight="400">{ex.prompt}</Text>
        {ex.hint && !result ? (
          <Row>
            <Lightbulb size={15} color={colors.mutedForeground} />
            <Text variant="small" tone="muted" style={{ flex: 1 }}>{ex.hint}</Text>
          </Row>
        ) : null}
        {ex.input === "choice" && ex.options ? (
          <ChoiceList options={ex.options} value={answer} onChange={setAnswer} disabled={!!result} correct={result ? result.correct_answer : undefined} />
        ) : (
          <Input
            value={answer}
            onChangeText={setAnswer}
            editable={!result}
            multiline={ex.input === "sentence"}
            placeholder={ex.input === "sentence" ? "Write your own sentence…" : "Type your answer"}
            accessibilityLabel={ex.input === "sentence" ? "Your sentence" : "Your answer"}
            autoCapitalize={ex.input === "sentence" ? "sentences" : "none"}
            autoCorrect={false}
            onSubmitEditing={() => !result && answer.trim() && review.mutate()}
          />
        )}
        {!result ? (
          <Row wrap>
            <Button title="Check" disabled={!answer.trim()} loading={review.isPending} onPress={() => review.mutate()} />
            <Button title="I already know this" variant="ghost" icon={SkipForward} loading={known.isPending} onPress={() => known.mutate()} />
          </Row>
        ) : null}
      </Card>

      {result ? (
        <Card style={{ borderColor: result.correct ? colors.success : colors.danger }}>
          <Row>
            {result.correct ? <CheckCircle2 size={20} color={colors.success} /> : <CircleX size={20} color={colors.danger} />}
            <Text weight="600" tone={result.correct ? "success" : "danger"} style={{ flex: 1 }}>
              {result.correct ? "Correct!" : `The answer is: ${result.correct_answer}`}
            </Text>
          </Row>
          {result.feedback ? <Text variant="small">{result.feedback}</Text> : null}
          <View style={{ backgroundColor: colors.muted, borderRadius: 12, padding: 12, gap: 4 }}>
            <Text variant="small">
              <Text variant="small" weight="700">{result.item.word}</Text> ({result.item.part_of_speech}) — {result.item.definition}
            </Text>
            <Text variant="small" tone="muted" style={{ fontStyle: "italic" }}>{result.item.example}</Text>
            {result.item.collocations.length ? <Text variant="small" tone="muted">Collocations: {result.item.collocations.slice(0, 3).join(" · ")}</Text> : null}
          </View>
          <Text variant="caption" tone="muted">
            {titleCase(result.state_before)} → {titleCase(result.state_after)} · next review {formatDateTime(result.next_review_at)}
          </Text>
          {explanation ? (
            <Notice tone="primary" icon={Sparkles}>
              <View style={{ gap: 4 }}>
                <Text variant="small">{explanation.explanation}</Text>
                {explanation.examples.map((e) => (
                  <Text key={e} variant="small">• {e}</Text>
                ))}
                {explanation.common_mistake ? <Text variant="small">Common mistake: {explanation.common_mistake}</Text> : null}
                {explanation.usage_tip ? <Text variant="small">Tip: {explanation.usage_tip}</Text> : null}
              </View>
            </Notice>
          ) : null}
          <Row wrap>
            <Button title={index + 1 >= session.exercises.length ? "Finish session" : "Next word"} icon={ArrowRight} onPress={next} />
            {!explanation ? <Button title="Explain this word" variant="ghost" icon={MessageCircleQuestion} loading={explain.isPending} onPress={() => explain.mutate(result.item.id)} /> : null}
          </Row>
        </Card>
      ) : null}
      <Text variant="caption" tone="muted">
        {score.correct}/{score.total} correct so far · +{score.xp} XP
      </Text>
    </View>
  );
}
