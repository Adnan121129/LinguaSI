import { useMutation, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { CheckCircle2, CircleX, RotateCcw, Shuffle, Trophy } from "lucide-react-native";
import { useMemo, useState } from "react";
import { Pressable, View } from "react-native";

import { SIActions, useToast } from "@/components/toast";
import { Badge, Button, Card, ChoiceList, ErrorState, Input, Notice, ProgressBar, Row, Text } from "@/components/ui";
import { useTimeOnTask } from "@/hooks/use-time-on-task";
import { api } from "@/lib/api";
import { QTYPE_LABELS } from "@/lib/constants";
import { appHref } from "@/lib/routes";
import { useTheme } from "@/lib/theme";
import type { PracticeItem, PracticeSet, PracticeSubmitResponse } from "@/lib/types";

/** Tap the words in order to rebuild a sentence; tap again to take a word back. */
function WordOrder({ prompt, value, onChange }: { prompt: string; value: string; onChange: (v: string) => void }) {
  const { colors } = useTheme();
  const tokens = useMemo(() => (prompt.split(": ").slice(1).join(": ") || prompt).split(" / ").map((t) => t.trim()).filter(Boolean), [prompt]);
  const [picked, setPicked] = useState<number[]>([]);
  const toggle = (index: number) => {
    const next = picked.includes(index) ? picked.filter((i) => i !== index) : [...picked, index];
    setPicked(next);
    onChange(next.map((i) => tokens[i]).join(" "));
  };
  return (
    <View style={{ gap: 10 }}>
      <View accessibilityLabel="Your sentence" accessibilityLiveRegion="polite" style={{ minHeight: 48, borderWidth: 1, borderStyle: "dashed", borderColor: colors.border, borderRadius: 12, padding: 12 }}>
        {value ? <Text>{value}</Text> : <Text tone="muted">Tap the words in the right order…</Text>}
      </View>
      <Row wrap>
        {tokens.map((token, i) => {
          const used = picked.includes(i);
          return (
            <Pressable
              key={`${token}-${i}`}
              onPress={() => toggle(i)}
              accessibilityRole="button"
              accessibilityState={{ selected: used }}
              accessibilityLabel={token}
              style={{ borderWidth: 1, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8, borderColor: used ? colors.primary : colors.border, backgroundColor: used ? colors.primarySoft : colors.card, opacity: used ? 0.6 : 1 }}
            >
              <Text variant="small" tone={used ? "primary" : "default"}>{token}</Text>
            </Pressable>
          );
        })}
        {picked.length ? (
          <Pressable
            onPress={() => {
              setPicked([]);
              onChange("");
            }}
            accessibilityRole="button"
            accessibilityLabel="Clear"
            style={{ flexDirection: "row", alignItems: "center", gap: 4, paddingHorizontal: 8, paddingVertical: 8 }}
          >
            <RotateCcw size={14} color={colors.mutedForeground} />
            <Text variant="small" tone="muted">Clear</Text>
          </Pressable>
        ) : null}
      </Row>
    </View>
  );
}

function ItemInput({ item, value, onChange }: { item: PracticeItem; value: string; onChange: (v: string) => void }) {
  if (item.qtype === "multiple_choice" && item.options) return <ChoiceList options={item.options} value={value} onChange={onChange} />;
  if (item.qtype === "sentence_order") return <WordOrder prompt={item.prompt} value={value} onChange={onChange} />;
  if (item.qtype === "gap_fill") return <Input value={value} onChangeText={onChange} placeholder="Type the missing word(s)" accessibilityLabel="Your answer" autoCapitalize="none" autoCorrect={false} />;
  return <Input value={value} onChangeText={onChange} multiline placeholder="Write the corrected sentence" accessibilityLabel="Your answer" />;
}

/** Runs any practice set (grammar drill, mistake repair challenge, revision session, Lab practice). */
export function PracticeRunner({ practice, exit = { href: "/mistakes", label: "Back to My Mistakes" } }: { practice: PracticeSet; exit?: { href: string; label: string } }) {
  const { colors } = useTheme();
  const queryClient = useQueryClient();
  const { celebrate } = useToast();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const elapsedSeconds = useTimeOnTask();
  const [result, setResult] = useState<PracticeSubmitResponse | null>(null);
  const submit = useMutation({
    mutationFn: () => api<PracticeSubmitResponse>(`/practice/sets/${practice.id}/submit`, { json: { answers, duration_seconds: elapsedSeconds() } }),
    onSuccess: (res) => {
      setResult(res);
      celebrate(res.outcome);
      queryClient.setQueryData(["practice", practice.id], res.practice);
      ["dashboard", "mistakes", "mistake-summary", "practice-list"].forEach((key) => queryClient.invalidateQueries({ queryKey: [key] }));
    },
  });

  const done = result?.practice ?? (practice.status === "completed" ? practice : null);
  if (done) {
    const byId = Object.fromEntries(done.results.map((r) => [r.id, r]));
    return (
      <View style={{ gap: 14 }}>
        <Card>
          <Row gap={14}>
            <View style={{ width: 56, height: 56, borderRadius: 16, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" }}>
              <Trophy size={26} color={colors.primary} />
            </View>
            <View style={{ flex: 1, gap: 4 }}>
              <Text style={{ fontSize: 28, fontWeight: "700" }}>
                {done.score} / {done.total}
              </Text>
              <Text variant="small" tone="muted">{Math.round(done.accuracy ?? 0)}% correct</Text>
            </View>
          </Row>
          <ProgressBar value={done.accuracy ?? 0} tone={(done.accuracy ?? 0) >= 80 ? "success" : "primary"} label="Accuracy" />
          {result && result.mastered_mistakes.length ? <Badge tone="success" label={`${result.mastered_mistakes.length} mistake(s) mastered`} /> : null}
        </Card>
        <SIActions outcome={result?.outcome} />
        {done.items.map((item, index) => {
          const r = byId[item.id];
          return (
            <Card key={item.id} style={{ borderColor: r?.correct ? colors.success : colors.danger }}>
              <Row style={{ alignItems: "flex-start" }}>
                {r?.correct ? <CheckCircle2 size={18} color={colors.success} accessibilityLabel="Correct" /> : <CircleX size={18} color={colors.danger} accessibilityLabel="Incorrect" />}
                <Text weight="600" style={{ flex: 1 }}>
                  {index + 1}. {item.prompt}
                </Text>
              </Row>
              {r ? (
                <View style={{ gap: 4, paddingLeft: 26 }}>
                  {!r.correct ? (
                    <Text variant="small">
                      <Text variant="small" tone="muted">Your answer: </Text>
                      {r.your_answer || "no answer"}
                    </Text>
                  ) : null}
                  <Text variant="small">
                    <Text variant="small" tone="muted">Answer: </Text>
                    <Text variant="small" tone="success" weight="600">{r.answer}</Text>
                  </Text>
                  {r.explanation ? <Text variant="small" tone="muted">{r.explanation}</Text> : null}
                </View>
              ) : null}
            </Card>
          );
        })}
        <Button title={exit.label} variant="outline" onPress={() => router.replace(appHref(exit.href))} />
        <Button title="Home" onPress={() => router.navigate("/")} />
      </View>
    );
  }

  const answered = practice.items.filter((i) => (answers[i.id] ?? "").trim()).length;
  return (
    <View style={{ gap: 14 }}>
      <Notice tone="primary" icon={Shuffle}>{practice.why}</Notice>
      {practice.items.map((item, index) => (
        <Card key={item.id}>
          <Row wrap>
            <Badge label={QTYPE_LABELS[item.qtype] ?? item.qtype} />
            {item.source === "personal" ? <Badge tone="warning" label="From your own work" /> : null}
          </Row>
          <Text weight="600">
            {index + 1}. {item.qtype === "sentence_order" ? "Put the words in the correct order." : item.prompt}
          </Text>
          <ItemInput item={item} value={answers[item.id] ?? ""} onChange={(v) => setAnswers((a) => ({ ...a, [item.id]: v }))} />
        </Card>
      ))}
      {submit.error ? <ErrorState error={submit.error} onRetry={() => submit.mutate()} /> : null}
      <Text variant="small" tone="muted">
        {answered} of {practice.items.length} answered
      </Text>
      <Button title="Check my answers" size="lg" loading={submit.isPending} onPress={() => submit.mutate()} />
    </View>
  );
}
