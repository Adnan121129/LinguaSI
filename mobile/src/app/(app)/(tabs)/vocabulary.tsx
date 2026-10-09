import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { Play, Plus, Search } from "lucide-react-native";
import { useState } from "react";
import { ActivityIndicator, ScrollView, View } from "react-native";

import { ChartCard, LineChart, shortDay } from "@/components/charts";
import { useToast } from "@/components/toast";
import { Badge, Button, Card, Chip, EmptyState, ErrorState, Input, PageHeader, Row, Screen, Segmented, Stat, Text, type Tone } from "@/components/ui";
import { useRefetchOnFocus } from "@/hooks/use-refetch-on-focus";
import { api, errorMessage } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import type { Page, UserWord, VocabInsights, VocabItem, VocabToday } from "@/lib/types";
import { formatDate, titleCase } from "@/lib/utils";

const STATES = ["new", "learning", "familiar", "strong", "mastered"] as const;
const STATE_TONE: Record<string, Tone> = { new: "accent", learning: "warning", familiar: "primary", strong: "success", mastered: "success" };
const GROUP_LABELS: Record<string, string> = {
  repeatedly_misunderstood: "Repeatedly misunderstood",
  forgotten: "Forgotten after learning",
  challenging: "Challenging",
  too_easy: "Too easy",
  in_progress: "In progress",
};
const BANK_TOPICS = ["academic", "argument", "collocation", "daily_life", "economy", "education", "environment", "health", "society", "technology", "work", "travel"];

type Tab = "today" | "words" | "bank" | "insights";


function Spinner() {
  const { colors } = useTheme();
  return <ActivityIndicator color={colors.primary} style={{ padding: 24 }} />;
}

function TodayTab({ focus }: { focus: string | null }) {
  const today = useQuery({ queryKey: ["vocab-today", focus], queryFn: () => api<VocabToday>(`/vocabulary/today${focus ? `?focus=${focus}` : ""}`) });
  useRefetchOnFocus(today.refetch);
  if (today.isLoading) return <Spinner />;
  if (today.error || !today.data) return <ErrorState error={today.error} onRetry={() => today.refetch()} />;
  const d = today.data;
  return (
    <>
      <Card>
        <Text variant="subheading">Today</Text>
        <Text variant="small" tone="muted">{focus === "collocation" ? "Focus: collocations for your writing" : "Due words first, then a few new ones"}</Text>
        <Row style={{ justifyContent: "space-between" }}>
          <Stat label="Due" value={d.due_count} />
          <Stat label="New" value={d.new_count} />
          <Stat label="Known" value={d.counts.known} />
          <Stat label="Recall" value={d.retention.accuracy === null ? "—" : `${Math.round(d.retention.accuracy)}%`} />
        </Row>
        <Text variant="caption" tone="muted">Recall accuracy over your last {d.retention.reviews} reviews.</Text>
        {d.exercises.length ? (
          <Button title={`Start review (${d.exercises.length} words)`} icon={Play} size="lg" onPress={() => router.push(focus ? `/vocabulary/review?focus=${focus}` : "/vocabulary/review")} />
        ) : (
          <EmptyState title="You're all caught up" description="No words are due right now. New words are added each day, or add some from the word bank." />
        )}
      </Card>
      <Text variant="small" tone="muted">
        Spaced repetition brings each word back just before you&apos;re likely to forget it. SI also adds words from your own writing and speaking.
      </Text>
    </>
  );
}

function WordsTab() {
  const [state, setState] = useState("");
  const words = useQuery({ queryKey: ["vocab-words", state], queryFn: () => api<Page<UserWord>>(`/vocabulary/words?page_size=100${state ? `&state=${state}` : ""}`) });
  return (
    <>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
        <Chip label="All" selected={!state} onPress={() => setState("")} />
        {STATES.map((s) => (
          <Chip key={s} label={titleCase(s)} selected={state === s} onPress={() => setState(s)} />
        ))}
      </ScrollView>
      {words.isLoading ? (
        <Spinner />
      ) : words.error ? (
        <ErrorState error={words.error} onRetry={() => words.refetch()} />
      ) : words.data?.items.length ? (
        <>
          <Text variant="small" tone="muted">{words.data.total} words</Text>
          {words.data.items.map((w) => (
            <Card key={w.user_vocab_id} style={{ gap: 6 }}>
              <Row style={{ alignItems: "flex-start" }}>
                <Text weight="600" style={{ flex: 1 }}>
                  {w.item.word} <Text variant="small" tone="muted">{w.item.part_of_speech} · {w.item.cefr}</Text>
                </Text>
                <Badge tone={STATE_TONE[w.state]} label={titleCase(w.state)} />
              </Row>
              <Text variant="small" tone="muted">{w.item.definition}</Text>
              <Text variant="caption" tone="muted">
                {w.correct_count} right · {w.incorrect_count} wrong · next {formatDate(w.due_at)}
                {w.used_in_writing + w.used_in_speaking > 0 ? ` · used ${w.used_in_writing}× in writing, ${w.used_in_speaking}× in speaking` : ""}
              </Text>
            </Card>
          ))}
        </>
      ) : (
        <EmptyState title="No words here yet" description="Start today's review to add your first words." />
      )}
    </>
  );
}

function BankTab() {
  const queryClient = useQueryClient();
  const { push } = useToast();
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [topic, setTopic] = useState("");
  const bank = useQuery({
    queryKey: ["vocab-bank", search, topic],
    queryFn: () => api<Page<VocabItem & { owned: boolean }>>(`/vocabulary/bank?page_size=30${search ? `&q=${encodeURIComponent(search)}` : ""}${topic ? `&topic=${topic}` : ""}`),
  });
  const add = useMutation({
    mutationFn: (itemId: number) => api("/vocabulary/words", { json: { item_id: itemId } }),
    onSuccess: () => {
      push({ tone: "success", title: "Added to your words", description: "It will appear in your next review." });
      queryClient.invalidateQueries({ queryKey: ["vocab-bank"] });
      queryClient.invalidateQueries({ queryKey: ["vocab-words"] });
    },
    onError: (err) => push({ tone: "error", title: "Couldn't add the word", description: errorMessage(err) }),
  });
  return (
    <>
      <Row>
        <View style={{ flex: 1 }}>
          <Input value={q} onChangeText={setQ} placeholder="Search words and phrases" accessibilityLabel="Search the word bank" returnKeyType="search" onSubmitEditing={() => setSearch(q.trim())} autoCapitalize="none" />
        </View>
        <Button title="Search" icon={Search} variant="secondary" onPress={() => setSearch(q.trim())} />
      </Row>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
        <Chip label="All topics" selected={!topic} onPress={() => setTopic("")} />
        {BANK_TOPICS.map((t) => (
          <Chip key={t} label={titleCase(t)} selected={topic === t} onPress={() => setTopic(t)} />
        ))}
      </ScrollView>
      {bank.isLoading ? (
        <Spinner />
      ) : bank.error ? (
        <ErrorState error={bank.error} onRetry={() => bank.refetch()} />
      ) : bank.data?.items.length ? (
        bank.data.items.map((item) => (
          <Card key={item.id} style={{ gap: 6 }}>
            <Row style={{ alignItems: "flex-start" }}>
              <Text weight="600" style={{ flex: 1 }}>
                {item.word} <Text variant="small" tone="muted">{item.part_of_speech} · {item.cefr}</Text>
              </Text>
              {item.owned ? <Badge tone="success" label="In your words" /> : <Button title="Add" icon={Plus} size="sm" variant="secondary" disabled={add.isPending} onPress={() => add.mutate(item.id)} accessibilityLabel={`Add ${item.word}`} />}
            </Row>
            <Text variant="small">{item.definition}</Text>
            <Text variant="small" tone="muted" style={{ fontStyle: "italic" }}>{item.example}</Text>
          </Card>
        ))
      ) : (
        <EmptyState title="No words found" description="Try another search or topic." />
      )}
    </>
  );
}

function InsightsTab() {
  const { colors } = useTheme();
  const insights = useQuery({ queryKey: ["vocab-insights"], queryFn: () => api<VocabInsights>("/vocabulary/insights") });
  if (insights.isLoading) return <Spinner />;
  if (insights.error || !insights.data) return <ErrorState error={insights.error} onRetry={() => insights.refetch()} />;
  const d = insights.data;
  return (
    <>
      <Card>
        <Row wrap gap={16}>
          {STATES.map((s) => (
            <Stat key={s} label={titleCase(s)} value={d.counts[s]} />
          ))}
          <Stat label="Recall" value={d.retention.accuracy === null ? "—" : `${Math.round(d.retention.accuracy)}%`} hint={`last ${d.retention.reviews} reviews`} />
        </Row>
      </Card>
      <ChartCard
        question="Is my vocabulary growing?"
        description="Words you know (familiar or better) and words mastered"
        rows={d.growth}
        columns={[
          { key: "day", label: "Day", format: (v) => shortDay(String(v)) },
          { key: "known", label: "Known" },
          { key: "mastered", label: "Mastered" },
        ]}
        legend={[
          { label: "Known", color: colors.series[0] },
          { label: "Mastered", color: colors.series[2] },
        ]}
      >
        <LineChart
          data={d.growth}
          xKey="day"
          xFormat={shortDay}
          series={[
            { key: "known", label: "Known", color: colors.series[0] },
            { key: "mastered", label: "Mastered", color: colors.series[2] },
          ]}
        />
      </ChartCard>
      {Object.entries(GROUP_LABELS).map(([key, label]) =>
        d.groups[key]?.length ? (
          <Card key={key}>
            <Text variant="subheading">{label}</Text>
            <Text variant="caption" tone="muted">{d.group_counts[key] ?? d.groups[key].length} words</Text>
            <Row wrap gap={6}>
              {d.groups[key].map((w) => (
                <Badge key={w} label={w} />
              ))}
            </Row>
          </Card>
        ) : null,
      )}
      {d.used_in_writing.length || d.used_in_speaking.length ? (
        <Card>
          <Text variant="subheading">Words you&apos;ve used in context</Text>
          <Text variant="caption" tone="muted">Using a word in writing or speaking counts as a successful review.</Text>
          {d.used_in_writing.length ? <Text variant="small">Writing: {d.used_in_writing.join(", ")}</Text> : null}
          {d.used_in_speaking.length ? <Text variant="small">Speaking: {d.used_in_speaking.join(", ")}</Text> : null}
        </Card>
      ) : null}
    </>
  );
}

export default function VocabularyTab() {
  const { focus } = useLocalSearchParams<{ focus?: string }>();
  const [tab, setTab] = useState<Tab>("today");
  return (
    <Screen safeTop>
      <PageHeader title="Vocabulary" subtitle="Adaptive spaced repetition with words from your own work." />
      <Segmented
        value={tab}
        onChange={setTab}
        options={[
          { value: "today", label: "Today" },
          { value: "words", label: "My words" },
          { value: "bank", label: "Bank" },
          { value: "insights", label: "Insights" },
        ]}
      />
      {tab === "today" ? <TodayTab focus={focus ?? null} /> : null}
      {tab === "words" ? <WordsTab /> : null}
      {tab === "bank" ? <BankTab /> : null}
      {tab === "insights" ? <InsightsTab /> : null}
    </Screen>
  );
}
