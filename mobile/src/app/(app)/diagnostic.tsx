import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { ArrowRight, CheckCircle2, ChevronLeft, Sparkles } from "lucide-react-native";
import { useState } from "react";
import { ScrollView, View } from "react-native";

import { BandValue } from "@/components/band";
import { ListeningPlayer } from "@/components/listening-player";
import { SIActions, useToast } from "@/components/toast";
import { Badge, Button, Card, ChoiceList, ErrorState, Input, ListRow, Loading, Notice, ProgressBar, Row, Screen, Text } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { appHref } from "@/lib/routes";
import { useTheme } from "@/lib/theme";
import type { DiagnosticItem, DiagnosticResult, DiagnosticStart } from "@/lib/types";
import { wordCount } from "@/lib/utils";

const SECTIONS = ["Vocabulary", "Grammar", "Reading", "Listening", "Writing", "Speaking"] as const;

function ItemList({ items, answers, setAnswer }: { items: DiagnosticItem[]; answers: Record<string, string>; setAnswer: (id: string, v: string) => void }) {
  return (
    <View style={{ gap: 20 }}>
      {items.map((item, index) => (
        <View key={item.id} style={{ gap: 8 }}>
          <Text weight="600">
            <Text tone="muted">{index + 1}. </Text>
            {item.prompt}
          </Text>
          <ChoiceList options={item.options ?? []} value={answers[item.id]} onChange={(v) => setAnswer(item.id, v)} />
        </View>
      ))}
    </View>
  );
}

function ResultView({ result }: { result: DiagnosticResult }) {
  const { colors } = useTheme();
  return (
    <Screen>
      <Row>
        <CheckCircle2 size={16} color={colors.primary} />
        <Text tone="primary" weight="600">Diagnostic complete</Text>
      </Row>
      <Text variant="title">Your starting point</Text>
      <Card>
        <Row style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
          <BandValue band={result.estimated_band} size="lg" label={result.label} />
          <View style={{ alignItems: "flex-end", gap: 2 }}>
            <Text variant="label" tone="muted">AI Estimated Level</Text>
            <Text style={{ fontSize: 34, fontWeight: "700" }}>{result.estimated_cefr ?? "—"}</Text>
          </View>
        </Row>
        <Badge tone={result.confidence === "high" ? "success" : result.confidence === "medium" ? "primary" : "warning"} label={`${result.confidence} confidence`} />
        <Text variant="caption" tone="muted">{result.disclaimer}</Text>
      </Card>
      <Card>
        <Text variant="subheading">Section results</Text>
        {result.sections.map((s) => (
          <View key={s.key} style={{ gap: 5 }}>
            <Row style={{ justifyContent: "space-between" }}>
              <Text variant="small" weight="600">{s.label}</Text>
              <Text variant="small" tone="muted">
                {s.band !== null && s.band !== undefined ? `Band ${s.band}` : s.score !== null ? `${Math.round(s.score)}/100` : "Not taken"}
                {s.total ? ` · ${s.correct}/${s.total}` : ""}
              </Text>
            </Row>
            <ProgressBar value={s.score ?? 0} label={`${s.label} score`} />
            {s.note ? <Text variant="caption" tone="muted">{s.note}</Text> : null}
          </View>
        ))}
      </Card>
      <Card>
        <Text variant="subheading">Strengths</Text>
        {result.strengths.map((s) => (
          <Text key={s} variant="small">• {s}</Text>
        ))}
        <Text variant="subheading">Focus areas</Text>
        {result.focus_areas.map((s) => (
          <Text key={s} variant="small">• {s}</Text>
        ))}
      </Card>
      {result.writing_feedback ? (
        <Card>
          <Text variant="subheading">Writing sample</Text>
          <Text variant="small" tone="muted">{result.writing_feedback.summary}</Text>
          {result.writing_feedback.top_errors.map((e) => (
            <Text key={e.original} variant="small">
              <Text variant="small" style={{ color: colors.danger, textDecorationLine: "line-through" }}>{e.original}</Text>
              {"  →  "}
              <Text variant="small" tone="success" weight="600">{e.corrected}</Text>
              {e.explanation ? <Text variant="small" tone="muted"> — {e.explanation}</Text> : null}
            </Text>
          ))}
        </Card>
      ) : null}
      <SIActions outcome={result.outcome} />
      <Card style={{ gap: 0, paddingVertical: 4 }}>
        <Row style={{ paddingTop: 10 }}>
          <Sparkles size={16} color={colors.primary} />
          <Text variant="subheading">Your next steps</Text>
        </Row>
        {result.next_steps.map((step) => (
          <ListRow key={step.title} title={step.title} subtitle={step.why} onPress={() => router.replace(appHref(step.route))} />
        ))}
      </Card>
      <Button title="Go to my dashboard" size="lg" onPress={() => router.navigate("/")} />
    </Screen>
  );
}

export default function DiagnosticScreen() {
  const { colors } = useTheme();
  const queryClient = useQueryClient();
  const { push, celebrate } = useToast();
  const [section, setSection] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [writing, setWriting] = useState("");
  const [speaking, setSpeaking] = useState<Record<string, string>>({});
  const start = useQuery({ queryKey: ["diagnostic-start"], queryFn: () => api<DiagnosticStart>("/diagnostic/start", { method: "POST" }), staleTime: Infinity, gcTime: 0, retry: 1 });
  const submit = useMutation({
    mutationFn: (attemptId: number) =>
      api<DiagnosticResult>(`/diagnostic/${attemptId}/submit`, {
        json: {
          answers,
          writing,
          speaking: Object.entries(speaking)
            .filter(([, text]) => text.trim())
            .map(([id, text]) => ({ id, transcript: text.trim(), duration_seconds: 0, source: "typed" })),
        },
      }),
    onSuccess: (result) => {
      celebrate(result.outcome);
      ["me", "dashboard"].forEach((key) => queryClient.invalidateQueries({ queryKey: [key] }));
    },
    onError: (err) => push({ tone: "error", title: "We couldn't score your diagnostic", description: errorMessage(err) }),
  });

  if (submit.data) return <ResultView result={submit.data} />;
  if (start.isLoading) return <Loading label="Preparing your diagnostic…" />;
  if (start.error || !start.data)
    return (
      <Screen>
        <ErrorState error={start.error} onRetry={() => start.refetch()} />
      </Screen>
    );

  const data = start.data;
  const setAnswer = (id: string, v: string) => setAnswers((a) => ({ ...a, [id]: v }));
  const words = wordCount(writing);
  const last = section === SECTIONS.length - 1;

  return (
    <Screen>
      <Text tone="primary" weight="600">Diagnostic · about 15 minutes</Text>
      <Text variant="title">{SECTIONS[section]}</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }} accessibilityLabel="Sections">
        {SECTIONS.map((name, i) => (
          <Badge key={name} tone={i === section ? "primary" : i < section ? "success" : "muted"} label={`${i + 1}. ${name}`} />
        ))}
      </ScrollView>
      <ProgressBar value={((section + 1) / SECTIONS.length) * 100} label="Diagnostic progress" />
      <Card style={{ gap: 16 }}>
        {section === 0 ? <ItemList items={data.vocabulary} answers={answers} setAnswer={setAnswer} /> : null}
        {section === 1 ? <ItemList items={data.grammar} answers={answers} setAnswer={setAnswer} /> : null}
        {section === 2 ? (
          <>
            <View style={{ backgroundColor: colors.muted, borderRadius: 14, padding: 12, gap: 6 }}>
              <Text weight="600">{data.reading.title}</Text>
              <Text variant="small" style={{ lineHeight: 21 }}>{data.reading.text}</Text>
            </View>
            <ItemList items={data.reading.questions} answers={answers} setAnswer={setAnswer} />
          </>
        ) : null}
        {section === 3 ? (
          <>
            <Text variant="small" tone="muted">{data.listening.title}. Listen to the conversation (you can play it twice), then answer the questions.</Text>
            <ListeningPlayer segments={data.listening.segments} speakers={data.listening.speakers} rate={0.95} mode="device" maxPlays={2} />
            <ItemList items={data.listening.questions} answers={answers} setAnswer={setAnswer} />
          </>
        ) : null}
        {section === 4 ? (
          <>
            <Text weight="600">{data.writing.prompt}</Text>
            <Text variant="small" tone="muted">
              Aim for at least {data.writing.min_words} words (about {data.writing.time_limit_minutes} minutes). Write naturally — this shows SI where to start.
            </Text>
            <Input value={writing} onChangeText={setWriting} multiline accessibilityLabel="Your writing" style={{ minHeight: 220 }} />
            <Text variant="small" tone={words >= data.writing.min_words ? "success" : "muted"}>{words} words</Text>
          </>
        ) : null}
        {section === 5 ? (
          <>
            <Notice tone="primary">Answer each question in 3–4 sentences. Type your answer, or tap the 🎤 key on your keyboard to say it and let your phone write it down.</Notice>
            {data.speaking.map((prompt) => (
              <View key={prompt.id} style={{ gap: 8 }}>
                <Text weight="600">{prompt.prompt}</Text>
                <Input value={speaking[prompt.id] ?? ""} onChangeText={(v) => setSpeaking((s) => ({ ...s, [prompt.id]: v }))} multiline placeholder="Your answer…" accessibilityLabel={prompt.prompt} />
              </View>
            ))}
          </>
        ) : null}
      </Card>
      <Row style={{ justifyContent: "space-between" }}>
        <Button title="Back" variant="ghost" icon={ChevronLeft} disabled={section === 0} onPress={() => setSection((s) => s - 1)} />
        {last ? <Button title="See my results" loading={submit.isPending} onPress={() => submit.mutate(data.attempt_id)} /> : <Button title="Next section" icon={ArrowRight} onPress={() => setSection((s) => s + 1)} />}
      </Row>
    </Screen>
  );
}
