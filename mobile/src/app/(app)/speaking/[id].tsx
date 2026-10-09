import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router, Stack, useLocalSearchParams } from "expo-router";
import { Hourglass, Square, Volume2 } from "lucide-react-native";
import { useCallback, useEffect, useRef, useState } from "react";
import { View } from "react-native";

import { AnswerRecorder, type SpokenAnswer } from "@/components/answer-recorder";
import { SpeakingEvaluation } from "@/components/speaking-evaluation";
import { SIActions, useToast } from "@/components/toast";
import { Badge, Button, Card, ErrorState, Notice, ProgressBar, QueryView, Row, Screen, Text } from "@/components/ui";
import { appendRecording } from "@/hooks/use-answer-recorder";
import { useMeta } from "@/hooks/use-meta";
import { api, errorMessage } from "@/lib/api";
import { speak, stopSpeaking } from "@/lib/speech";
import { useTheme } from "@/lib/theme";
import type { ActivityOutcome, SpeakingSession, Transcript, Turn } from "@/lib/types";
import { formatDuration } from "@/lib/utils";

function PrepTimer({ seconds, onDone }: { seconds: number; onDone: () => void }) {
  const { colors } = useTheme();
  const [left, setLeft] = useState(seconds);
  useEffect(() => {
    if (left <= 0) {
      onDone();
      return;
    }
    const id = setTimeout(() => setLeft((l) => l - 1), 1000);
    return () => clearTimeout(id);
  }, [left, onDone]);
  return (
    <Card tone="warning">
      <Row>
        <Hourglass size={18} color={colors.warning} />
        <Text style={{ flex: 1 }}>
          Preparation time: <Text weight="700" style={{ fontVariant: ["tabular-nums"] }}>{formatDuration(left)}</Text>
        </Text>
      </Row>
      <Text variant="small">Make short notes, then speak for up to two minutes.</Text>
      <Button title="I'm ready" size="sm" variant="outline" onPress={onDone} style={{ alignSelf: "flex-start" }} />
    </Card>
  );
}

function TestRunner({ session, onFinished }: { session: SpeakingSession; onFinished: (outcome: ActivityOutcome) => void }) {
  const { colors } = useTheme();
  const queryClient = useQueryClient();
  const { push, celebrate } = useToast();
  const meta = useMeta();
  const serverStt = meta.data ? meta.data.speech.stt_provider !== "mock" : false;
  const [turn, setTurn] = useState<Turn | null>(session.current_turn);
  const [answers, setAnswers] = useState<Transcript[]>(session.transcripts);
  const [preparing, setPreparing] = useState(false);
  const spoken = useRef<string | null>(null);
  const endPreparation = useCallback(() => setPreparing(false), []);
  const say = useCallback((text: string) => speak(text, { rate: 0.95 }), []);

  useEffect(() => () => stopSpeaking(), []);

  // The examiner reads each new question aloud; Part 2 starts with a one-minute preparation.
  useEffect(() => {
    if (!turn) return;
    const key = `${turn.index}-${turn.is_followup}-${turn.question}`;
    if (spoken.current === key) return;
    spoken.current = key;
    setPreparing(turn.kind === "cue_card" && turn.prep_seconds > 0);
    void say(turn.examiner_text);
  }, [turn, say]);

  const finish = useMutation({
    mutationFn: () => api<{ session: SpeakingSession; outcome: ActivityOutcome }>("/speaking/session/finish", { json: { session_id: session.id } }),
    onSuccess: (res) => {
      stopSpeaking();
      queryClient.setQueryData(["speaking-session", session.id], res.session);
      ["dashboard", "speaking-history", "mistakes", "mistake-summary"].forEach((k) => queryClient.invalidateQueries({ queryKey: [k] }));
      celebrate(res.outcome);
      onFinished(res.outcome);
    },
    onError: () => queryClient.invalidateQueries({ queryKey: ["speaking-session", session.id] }),
  });

  const respond = useMutation({
    mutationFn: async (answer: SpokenAnswer) => {
      const form = new FormData();
      form.append("session_id", String(session.id));
      if (answer.transcript) form.append("transcript", answer.transcript);
      if (answer.source) form.append("transcript_source", answer.source);
      if (answer.recording) {
        if (answer.recording.durationSeconds) form.append("duration_seconds", String(answer.recording.durationSeconds));
        if (answer.recording.pauses) form.append("pauses", JSON.stringify(answer.recording.pauses));
        await appendRecording(form, answer.recording);
      }
      return api<{ transcript: Transcript; next: Turn | null; done: boolean }>("/speaking/session/respond", { form });
    },
    onSuccess: (res) => {
      setAnswers((a) => [...a, res.transcript]);
      if (res.done) finish.mutate();
      else setTurn(res.next);
    },
    onError: (err) => push({ tone: "error", title: "Your answer wasn't sent", description: errorMessage(err) }),
  });

  const abandon = useMutation({
    mutationFn: () => api(`/speaking/session/${session.id}/abandon`, { method: "POST" }),
    onSuccess: () => {
      stopSpeaking();
      queryClient.invalidateQueries({ queryKey: ["speaking-history"] });
      router.back();
    },
  });

  if (finish.isPending) {
    return (
      <Card>
        <Text variant="heading">The examiner is reviewing your answers…</Text>
        <Text variant="small" tone="muted">Analysing fluency, vocabulary, grammar and pronunciation evidence.</Text>
        <ProgressBar value={70} label="Evaluating" />
      </Card>
    );
  }
  if (finish.error) return <ErrorState title="Evaluation didn't finish" error={finish.error} onRetry={() => finish.mutate()} />;
  if (!turn) {
    return (
      <Card>
        <Text>All questions are answered.</Text>
        <Button title="Get my evaluation" onPress={() => finish.mutate()} />
      </Card>
    );
  }

  return (
    <View style={{ gap: 14 }}>
      <Row wrap>
        <Badge tone="primary" label={`Part ${turn.part}`} />
        <Text variant="small" tone="muted">
          Question {Math.min(turn.index + 1, turn.total)} of {turn.total}
          {turn.is_followup ? " · follow-up" : ""}
        </Text>
      </Row>
      <ProgressBar value={(turn.index / turn.total) * 100} label="Test progress" />
      <Card>
        <Row style={{ alignItems: "flex-start" }} gap={12}>
          <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" }}>
            <Text weight="700" tone="primary" variant="small">EX</Text>
          </View>
          <View style={{ flex: 1, gap: 4 }}>
            <Text variant="label" tone="muted">Examiner</Text>
            <Text variant="subheading" weight="400">{turn.examiner_text}</Text>
          </View>
        </Row>
        <Button title="Repeat the question" icon={Volume2} size="sm" variant="ghost" onPress={() => say(turn.examiner_text)} style={{ alignSelf: "flex-start" }} />
        {turn.kind === "cue_card" && turn.cue_card ? (
          <View style={{ borderWidth: 2, borderStyle: "dashed", borderColor: colors.primary + "66", borderRadius: 16, padding: 14, gap: 6 }}>
            <Text weight="600">{turn.cue_card.title}</Text>
            <Text variant="small">{turn.cue_card.prompt}</Text>
            <Text variant="small" tone="muted">You should say:</Text>
            {turn.cue_card.bullets.map((b) => (
              <Text key={b} variant="small">
                • {b}
              </Text>
            ))}
          </View>
        ) : null}
      </Card>
      {session.target_expressions.length && turn.index === 0 && !turn.is_followup ? (
        <Notice tone="primary">Try to use naturally: {session.target_expressions.map((e) => `“${e}”`).join(", ")} — words from your vocabulary list.</Notice>
      ) : null}
      {preparing ? (
        <PrepTimer seconds={turn.prep_seconds} onDone={endPreparation} />
      ) : (
        <Card>
          <AnswerRecorder
            key={`${turn.index}-${turn.is_followup}`}
            serverStt={serverStt}
            busy={respond.isPending}
            maxSeconds={turn.max_seconds}
            onAnswer={async (answer) => {
              stopSpeaking();
              await respond.mutateAsync(answer);
            }}
          />
        </Card>
      )}
      <Text variant="caption" tone="muted">
        Like the real test, there are no scores until the end. {answers.length} answer{answers.length === 1 ? "" : "s"} saved.
      </Text>
      <Row wrap>
        {answers.length ? <Button title="Finish early & evaluate" icon={Square} size="sm" variant="outline" onPress={() => finish.mutate()} /> : null}
        <Button title="Quit test" size="sm" variant="ghost" loading={abandon.isPending} onPress={() => abandon.mutate()} />
      </Row>
    </View>
  );
}

export default function SpeakingSessionScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const sessionId = Number(id);
  const queryClient = useQueryClient();
  const [outcome, setOutcome] = useState<ActivityOutcome | null>(null);
  const session = useQuery({ queryKey: ["speaking-session", sessionId], queryFn: () => api<SpeakingSession>(`/speaking/sessions/${sessionId}`), staleTime: Infinity });
  const retry = useMutation({
    mutationFn: () => api<{ session: SpeakingSession; outcome: ActivityOutcome }>("/speaking/session/finish", { json: { session_id: sessionId } }),
    onSuccess: (res) => {
      queryClient.setQueryData(["speaking-session", sessionId], res.session);
      setOutcome(res.outcome);
    },
  });
  return (
    <QueryView query={session}>
      {(data) => (
        <Screen>
          <Stack.Screen options={{ title: data.status === "completed" ? "Speaking evaluation" : "Speaking test" }} />
          <Text variant="small" tone="muted">Topic: {data.topic}</Text>
          {data.status === "completed" && data.evaluation ? (
            <>
              <SIActions outcome={outcome} />
              <SpeakingEvaluation session={data} />
            </>
          ) : data.status === "evaluation_failed" ? (
            <>
              <Notice tone="warning">AI speaking analysis was temporarily unavailable. Your answers are saved — you can run the evaluation again.</Notice>
              {retry.error ? <ErrorState error={retry.error} /> : null}
              <Button title="Evaluate my answers" loading={retry.isPending} onPress={() => retry.mutate()} />
            </>
          ) : data.status === "abandoned" ? (
            <Notice tone="muted">This test was ended without an evaluation.</Notice>
          ) : (
            <TestRunner key={data.id} session={data} onFinished={setOutcome} />
          )}
        </Screen>
      )}
    </QueryView>
  );
}
