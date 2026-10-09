import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Stack, useLocalSearchParams } from "expo-router";
import { Info } from "lucide-react-native";
import { useState } from "react";
import { View } from "react-native";

import { BandValue } from "@/components/band";
import { QuestionForm, withEvidence } from "@/components/comprehension";
import { ListeningPlayer } from "@/components/listening-player";
import { SIActions, useToast } from "@/components/toast";
import { Button, Card, Notice, QueryView, Row, Screen, Text } from "@/components/ui";
import { useTimeOnTask } from "@/hooks/use-time-on-task";
import { api, errorMessage } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import type { ActivityOutcome, ListeningAttempt, QuestionResult } from "@/lib/types";
import { percent, titleCase } from "@/lib/utils";

function Attempt({ data }: { data: ListeningAttempt }) {
  const { colors } = useTheme();
  const queryClient = useQueryClient();
  const { push, celebrate } = useToast();
  const elapsedSeconds = useTimeOnTask();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [plays, setPlays] = useState(0);
  const [evidence, setEvidence] = useState<QuestionResult | null>(null);
  const [outcome, setOutcome] = useState<ActivityOutcome | null>(null);
  const [showTranscript, setShowTranscript] = useState(false);
  const submitted = data.status === "submitted";
  const script = data.script;
  const speakerName = (sid: string) => script.speakers.find((s) => s.id === sid)?.name ?? sid;

  const replay = useMutation({ mutationFn: () => api(`/listening/attempts/${data.id}/replay`, { method: "POST" }) });
  const submit = useMutation({
    mutationFn: () =>
      api<{ attempt: ListeningAttempt; outcome: ActivityOutcome }>("/listening/submit", {
        json: { attempt_id: data.id, answers, time_spent_seconds: Math.min(elapsedSeconds(), 14400), replays: Math.max(0, plays - 1) },
      }),
    onSuccess: (res) => {
      queryClient.setQueryData(["listening-attempt", data.id], res.attempt);
      setOutcome(res.outcome);
      celebrate(res.outcome);
      ["dashboard", "listening-history", "mistakes", "mistake-summary"].forEach((k) => queryClient.invalidateQueries({ queryKey: [k] }));
    },
    onError: (err) => push({ tone: "error", title: "Couldn't submit your answers", description: errorMessage(err) }),
  });

  return (
    <Screen>
      <Stack.Screen options={{ title: script.title }} />
      <Text variant="small" tone="muted">
        {titleCase(script.scenario)} · level {data.difficulty} · {titleCase(script.accent)} accent
      </Text>
      {data.notice ? <Notice tone="muted" icon={Info}>{data.notice}</Notice> : null}
      {submitted ? (
        <Card>
          <Row style={{ justifyContent: "space-between" }}>
            <BandValue band={data.band} />
            <View style={{ alignItems: "flex-end" }}>
              <Text variant="heading">
                {data.correct} / {data.total}
              </Text>
              <Text variant="small" tone="muted">
                {percent(data.accuracy)} correct · played {data.replays + 1} time{data.replays ? "s" : ""}
              </Text>
            </View>
          </Row>
          <Text variant="caption" tone="muted">Band estimates for short practice sets are approximate indicators, not official scores.</Text>
        </Card>
      ) : null}
      <SIActions outcome={outcome} />
      <Card>
        <Text variant="subheading">The recording</Text>
        <Text variant="small" tone="muted">{script.context}</Text>
        <ListeningPlayer
          segments={script.segments.map((s) => ({ speaker: s.speaker, text: s.text, audio_url: s.audio_url }))}
          speakers={script.speakers}
          rate={script.speech_rate}
          mode={script.audio_mode}
          onPlay={(count) => {
            setPlays(count);
            if (count > 1 && !submitted) replay.mutate();
          }}
        />
        {!submitted ? <Text variant="caption" tone="muted">In the real test you hear the recording once. Replays are allowed here but are noted in your results.</Text> : null}
      </Card>
      {submitted || (showTranscript && script.audio_mode === "device") ? (
        <Card>
          <Text variant="subheading">Transcript</Text>
          {submitted ? <Text variant="caption" tone="muted">Tap an answer&apos;s evidence to highlight it here.</Text> : null}
          {script.segments.map((seg) => (
            <Text key={seg.index} variant="small" style={{ lineHeight: 21 }}>
              <Text variant="small" weight="700">{speakerName(seg.speaker)}: </Text>
              {seg.text ? withEvidence(seg.text, evidence?.evidence ?? null, colors.successSoft) : null}
            </Text>
          ))}
        </Card>
      ) : script.audio_mode === "device" ? (
        <Button title="Audio not playing? Read the transcript" variant="ghost" size="sm" onPress={() => setShowTranscript(true)} style={{ alignSelf: "flex-start" }} />
      ) : null}
      <Card>
        <QuestionForm questions={data.questions} answers={answers} onChange={(qid, v) => setAnswers((a) => ({ ...a, [qid]: v }))} results={submitted ? data.results : undefined} onShowEvidence={setEvidence} />
      </Card>
      {!submitted ? (
        <>
          <Text variant="small" tone="muted">
            {Object.values(answers).filter((v) => v.trim()).length} of {data.questions.length} answered
          </Text>
          <Button title="Submit answers" size="lg" loading={submit.isPending} onPress={() => submit.mutate()} />
        </>
      ) : null}
    </Screen>
  );
}

export default function ListeningAttemptScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const attemptId = Number(id);
  const attempt = useQuery({ queryKey: ["listening-attempt", attemptId], queryFn: () => api<ListeningAttempt>(`/listening/attempts/${attemptId}`), staleTime: Infinity });
  return <QueryView query={attempt}>{(data) => <Attempt key={data.id} data={data} />}</QueryView>;
}
