import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Stack, useLocalSearchParams } from "expo-router";
import { Clock, Info } from "lucide-react-native";
import { useEffect, useState } from "react";
import { View } from "react-native";

import { BandValue } from "@/components/band";
import { QuestionForm, spotlight, withEvidence } from "@/components/comprehension";
import { SIActions, useToast } from "@/components/toast";
import { Badge, Button, Card, Notice, QueryView, Row, Screen, Segmented, Text } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import type { ActivityOutcome, QuestionResult, ReadingAttempt } from "@/lib/types";
import { formatDuration, percent } from "@/lib/utils";

function Attempt({ data }: { data: ReadingAttempt }) {
  const { colors } = useTheme();
  const queryClient = useQueryClient();
  const { push, celebrate } = useToast();
  const [view, setView] = useState<"passage" | "questions">("passage");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [evidence, setEvidence] = useState<QuestionResult | null>(null);
  const [outcome, setOutcome] = useState<ActivityOutcome | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const submitted = data.status === "submitted";

  useEffect(() => {
    if (submitted) return;
    const started = new Date(data.started_at).getTime();
    const tick = () => setElapsed(Math.round((Date.now() - started) / 1000));
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [data.started_at, submitted]);

  const submit = useMutation({
    mutationFn: () => api<{ attempt: ReadingAttempt; outcome: ActivityOutcome }>("/reading/submit", { json: { attempt_id: data.id, answers, time_spent_seconds: Math.min(elapsed, 14400) } }),
    onSuccess: (res) => {
      queryClient.setQueryData(["reading-attempt", data.id], res.attempt);
      setOutcome(res.outcome);
      celebrate(res.outcome);
      ["dashboard", "reading-history", "mistakes", "mistake-summary"].forEach((k) => queryClient.invalidateQueries({ queryKey: [k] }));
    },
    onError: (err) => push({ tone: "error", title: "Couldn't submit your answers", description: errorMessage(err) }),
  });

  const remaining = data.time_limit_minutes * 60 - elapsed;
  const answered = Object.values(answers).filter((v) => v.trim()).length;

  return (
    <Screen>
      <Stack.Screen options={{ title: data.passage.title }} />
      <Row style={{ justifyContent: "space-between" }}>
        <Text variant="small" tone="muted">
          Level {data.difficulty} · {data.passage.word_count} words · {data.questions.length} questions
        </Text>
        {!submitted ? (
          <Row gap={4}>
            <Clock size={13} color={remaining < 0 ? colors.danger : colors.mutedForeground} />
            <Text variant="small" tone={remaining < 0 ? "danger" : remaining < 120 ? "warning" : "muted"} style={{ fontVariant: ["tabular-nums"] }}>
              {remaining >= 0 ? `${formatDuration(remaining)} left` : `${formatDuration(-remaining)} over`}
            </Text>
          </Row>
        ) : null}
      </Row>
      {data.notice ? <Notice tone="muted" icon={Info}>{data.notice}</Notice> : null}
      {submitted ? (
        <Card>
          <Row style={{ justifyContent: "space-between" }}>
            <BandValue band={data.band} />
            <View style={{ alignItems: "flex-end" }}>
              <Text variant="heading">
                {data.correct} / {data.total}
              </Text>
              <Text variant="small" tone="muted">{percent(data.accuracy)} correct</Text>
            </View>
          </Row>
          <Text variant="caption" tone="muted">Band estimates for short practice sets are approximate indicators, not official scores.</Text>
        </Card>
      ) : null}
      <SIActions outcome={outcome} />
      <Segmented
        value={view}
        onChange={setView}
        options={[
          { value: "passage", label: "Passage" },
          { value: "questions", label: submitted ? "Results" : `Questions (${answered}/${data.questions.length})` },
        ]}
      />
      {view === "passage" ? (
        <Card style={{ gap: 14 }}>
          {data.passage.paragraphs.map((p) => (
            <View key={p.label} style={evidence?.evidence_paragraph === p.label ? { backgroundColor: colors.successSoft, borderRadius: 10, padding: 8 } : undefined}>
              <Text style={{ lineHeight: 24 }}>
                <Text weight="700" tone="primary">{p.label}  </Text>
                {evidence ? withEvidence(p.text, evidence.evidence, colors.successSoft) : spotlight(p.text, data.spotlight, { fg: colors.accent, bg: colors.accentSoft })}
              </Text>
            </View>
          ))}
          {data.spotlight.length && !evidence ? <Text variant="caption" tone="muted">Highlighted: words from your vocabulary list.</Text> : null}
          {data.passage.headings.length && !submitted ? (
            <View style={{ gap: 4 }}>
              <Text weight="600">List of headings</Text>
              {data.passage.headings.map((h) => (
                <Text key={h} variant="small">{h}</Text>
              ))}
            </View>
          ) : null}
          <Button title={submitted ? "See results" : "Go to questions"} variant="secondary" onPress={() => setView("questions")} />
        </Card>
      ) : (
        <>
          <Card>
            <QuestionForm
              questions={data.questions}
              answers={answers}
              onChange={(qid, v) => setAnswers((a) => ({ ...a, [qid]: v }))}
              results={submitted ? data.results : undefined}
              headings={data.passage.headings}
              onShowEvidence={(r) => {
                setEvidence(r);
                setView("passage");
              }}
            />
          </Card>
          {!submitted ? (
            <>
              <Text variant="small" tone="muted">
                {answered} of {data.questions.length} answered
              </Text>
              <Button title="Submit answers" size="lg" loading={submit.isPending} onPress={() => submit.mutate()} />
            </>
          ) : (
            <Badge tone="primary" label="Tap a quote to see it in the passage" />
          )}
        </>
      )}
    </Screen>
  );
}

export default function ReadingAttemptScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const attemptId = Number(id);
  const attempt = useQuery({ queryKey: ["reading-attempt", attemptId], queryFn: () => api<ReadingAttempt>(`/reading/attempts/${attemptId}`), staleTime: Infinity });
  return <QueryView query={attempt}>{(data) => <Attempt key={data.id} data={data} />}</QueryView>;
}
