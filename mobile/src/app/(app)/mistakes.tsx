import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { CalendarClock, CheckCircle2, ChevronDown, ChevronUp, Dumbbell, RotateCcw, Sparkles } from "lucide-react-native";
import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, View } from "react-native";

import { ChartCard, ColumnChart, HeatmapGrid, shortWeek } from "@/components/charts";
import { useToast } from "@/components/toast";
import { Badge, Button, Card, Chip, EmptyState, ErrorState, Loading, Row, Screen, Stat, StatGrid, Text } from "@/components/ui";
import { ApiError, api, errorMessage } from "@/lib/api";
import { appHref } from "@/lib/routes";
import { useTheme } from "@/lib/theme";
import type { Mistake, MistakeDetail, MistakeSummary, Page, PracticeSet } from "@/lib/types";
import { relativeTime, titleCase } from "@/lib/utils";

const STATUS_TONE = { unresolved: "warning", corrected: "primary", mastered: "success" } as const;
const STATUS_FILTERS = [
  ["", "All"],
  ["unresolved", "To fix"],
  ["recurring", "Recurring"],
  ["due", "Due"],
  ["corrected", "Corrected"],
  ["mastered", "Mastered"],
] as const;
const SOURCES = ["writing", "speaking", "vocabulary", "reading", "listening", "practice"];

function MistakeRow({ mistake, open, onToggle }: { mistake: Mistake; open: boolean; onToggle: () => void }) {
  const { colors } = useTheme();
  const queryClient = useQueryClient();
  const { push } = useToast();
  const detail = useQuery({ queryKey: ["mistake", mistake.id], queryFn: () => api<MistakeDetail>(`/mistakes/${mistake.id}`), enabled: open });
  const refresh = () => ["mistakes", "mistake-summary", "dashboard"].forEach((key) => queryClient.invalidateQueries({ queryKey: [key] }));
  const status = useMutation({
    mutationFn: (body: { status?: string; revisit_in_days?: number }) => api<Mistake>(`/mistakes/${mistake.id}/status`, { json: body }),
    onSuccess: (_, body) => {
      push({ tone: "success", title: body.revisit_in_days ? `We'll bring this back in ${body.revisit_in_days} days` : body.status === "mastered" ? "Marked as mastered" : "Reopened" });
      refresh();
    },
    onError: (err) => push({ tone: "error", title: "Couldn't update this mistake", description: errorMessage(err) }),
  });
  const practise = useMutation({
    mutationFn: () => api<PracticeSet>(`/mistakes/${mistake.id}/practice`, { method: "POST" }),
    onSuccess: (ps) => router.push(`/practice/${ps.id}`),
    onError: (err) => {
      if (err instanceof ApiError && err.code === "use_skill_practice") router.push(appHref((err.details as { route: string }).route));
      else push({ tone: "error", title: "Couldn't build practice", description: errorMessage(err) });
    },
  });
  const skillPractice = mistake.category === "comprehension" || mistake.category === "fluency";

  return (
    <View style={{ borderTopWidth: 1, borderTopColor: colors.border, paddingVertical: 12, gap: 10 }}>
      <Pressable onPress={onToggle} accessibilityRole="button" accessibilityState={{ expanded: open }} style={{ flexDirection: "row", gap: 10, alignItems: "flex-start" }}>
        <View style={{ flex: 1, gap: 6 }}>
          <Text variant="small">
            <Text variant="small" style={{ backgroundColor: colors.dangerSoft, color: colors.danger }}>{mistake.original}</Text>
            {!skillPractice ? (
              <>
                {"  →  "}
                <Text variant="small" tone="success" weight="600">{mistake.corrected}</Text>
              </>
            ) : null}
          </Text>
          <Row wrap gap={6}>
            <Badge label={mistake.label} />
            <Text variant="caption" tone="muted">
              {titleCase(mistake.source)} · {relativeTime(mistake.last_seen_at)}
            </Text>
            {mistake.occurrences > 1 ? <Badge tone="danger" label={`×${mistake.occurrences}`} /> : null}
          </Row>
        </View>
        <Badge tone={STATUS_TONE[mistake.status]} label={titleCase(mistake.status)} />
        {open ? <ChevronUp size={16} color={colors.mutedForeground} /> : <ChevronDown size={16} color={colors.mutedForeground} />}
      </Pressable>
      {open ? (
        <View style={{ gap: 10 }}>
          <Text variant="small">{mistake.explanation}</Text>
          {mistake.context ? (
            <View style={{ backgroundColor: colors.muted, borderRadius: 12, padding: 10 }}>
              <Text variant="small" tone="muted">“{mistake.context}”</Text>
            </View>
          ) : null}
          {detail.isLoading ? (
            <ActivityIndicator color={colors.primary} />
          ) : detail.data?.guide ? (
            <View style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 10, gap: 4 }}>
              <Text variant="small" weight="600">{detail.data.guide.title ?? mistake.label}</Text>
              {detail.data.guide.rule ? <Text variant="small">{detail.data.guide.rule}</Text> : null}
              {detail.data.guide.tip ? <Text variant="small" tone="muted">Tip: {detail.data.guide.tip}</Text> : null}
            </View>
          ) : null}
          <Text variant="caption" tone="muted">
            Practised {mistake.practice_attempts} time{mistake.practice_attempts === 1 ? "" : "s"} · {mistake.practice_correct} correct · two correct practices in a row mark it as mastered.
          </Text>
          <Row wrap>
            <Button title={skillPractice ? "Practise this question type" : "Mini practice"} icon={Dumbbell} size="sm" loading={practise.isPending} onPress={() => practise.mutate()} />
            {mistake.status !== "mastered" ? (
              <Button title="Mark mastered" icon={CheckCircle2} size="sm" variant="outline" disabled={status.isPending} onPress={() => status.mutate({ status: "mastered" })} />
            ) : (
              <Button title="Reopen" icon={RotateCcw} size="sm" variant="outline" disabled={status.isPending} onPress={() => status.mutate({ status: "unresolved" })} />
            )}
            <Button title="Revisit in 3 days" icon={CalendarClock} size="sm" variant="ghost" disabled={status.isPending} onPress={() => status.mutate({ revisit_in_days: 3 })} />
          </Row>
        </View>
      ) : null}
    </View>
  );
}

export default function MistakesScreen() {
  const params = useLocalSearchParams<{ status?: string; focus?: string }>();
  const { push } = useToast();
  const [status, setStatus] = useState(params.status ?? "");
  const [category, setCategory] = useState("");
  const [source, setSource] = useState("");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<number | null>(Number(params.focus) || null);

  const summary = useQuery({ queryKey: ["mistake-summary"], queryFn: () => api<MistakeSummary>("/mistakes/summary") });
  const query = new URLSearchParams({ page: String(page), page_size: "15" });
  if (status) query.set("status", status);
  if (category) query.set("category", category);
  if (source) query.set("source", source);
  const list = useQuery({ queryKey: ["mistakes", status, category, source, page], queryFn: () => api<Page<Mistake>>(`/mistakes?${query}`) });

  const revision = useMutation({
    mutationFn: () => api<PracticeSet>("/mistakes/revision", { method: "POST" }),
    onSuccess: (ps) => router.push(`/practice/${ps.id}`),
    onError: (err) => push({ tone: "warning", title: "No revision session yet", description: errorMessage(err) }),
  });

  if (summary.isLoading) return <Loading />;
  if (summary.error || !summary.data)
    return (
      <Screen>
        <ErrorState error={summary.error} onRetry={() => summary.refetch()} />
      </Screen>
    );
  const s = summary.data;
  const filter = (set: (v: string) => void) => (value: string) => {
    set(value);
    setPage(1);
  };

  return (
    <Screen
      refreshing={summary.isRefetching || list.isRefetching}
      onRefresh={() => {
        summary.refetch();
        list.refetch();
      }}
    >
      <Text tone="muted">Every mistake from writing, speaking, vocabulary, reading and listening — grouped, tracked and practised until you master it.</Text>
      <Button title={`5-minute revision${s.due_for_revision ? ` (${s.due_for_revision} due)` : ""}`} icon={Sparkles} loading={revision.isPending} onPress={() => revision.mutate()} />
      <Card>
        <StatGrid>
          <Stat label="Tracked" value={s.totals.total} hint={`${s.totals.occurrences} occurrences`} />
          <Stat label="To fix" value={s.totals.unresolved} />
          <Stat label="Corrected" value={s.totals.corrected} />
          <Stat label="Mastered" value={s.totals.mastered} />
        </StatGrid>
      </Card>

      {s.totals.total === 0 ? (
        <EmptyState title="No mistakes tracked yet" description="Complete a writing task, a speaking test or some practice and SI will start tracking your patterns here." />
      ) : (
        <>
          <ChartCard
            question="Which kinds of mistakes do I make most?"
            description="All tracked mistakes by category"
            rows={s.by_category}
            columns={[
              { key: "label", label: "Category" },
              { key: "count", label: "Mistakes" },
            ]}
          >
            <ColumnChart data={s.by_category} xKey="label" yKey="count" label="Mistakes by category" height={190} />
          </ChartCard>
          <ChartCard
            question="Am I making fewer mistakes?"
            description="New mistakes recorded per week"
            rows={s.weekly_trend}
            columns={[
              { key: "week", label: "Week", format: (v) => shortWeek(String(v)) },
              { key: "count", label: "New mistakes" },
            ]}
          >
            <ColumnChart data={s.weekly_trend} xKey="week" yKey="count" label="New mistakes per week" xFormat={shortWeek} />
          </ChartCard>
          <ChartCard
            question="When and where do my mistakes happen?"
            description="Mistakes per category each week — darker means more"
            rows={s.heatmap.rows.map((r) => ({ label: r.label, ...Object.fromEntries(s.heatmap.weeks.map((w, i) => [w, r.values[i]])) }))}
            columns={[{ key: "label", label: "Category" }, ...s.heatmap.weeks.map((w) => ({ key: w, label: shortWeek(w) }))]}
          >
            <HeatmapGrid columns={s.heatmap.weeks} rows={s.heatmap.rows} />
          </ChartCard>
          {s.recurring.length ? (
            <Card>
              <Text variant="subheading">Recurring patterns</Text>
              <Text variant="caption" tone="muted">Mistakes you keep making in the last 60 days</Text>
              {s.recurring.map((r) => (
                <View key={r.subcategory} style={{ gap: 2 }}>
                  <Row style={{ justifyContent: "space-between" }}>
                    <Text weight="600">{r.label}</Text>
                    <Badge tone="danger" label={`${r.count}×`} />
                  </Row>
                  {r.example ? (
                    <Text variant="small" tone="muted">
                      e.g. “{r.example.original}” → “{r.example.corrected}”
                    </Text>
                  ) : null}
                </View>
              ))}
            </Card>
          ) : null}
        </>
      )}

      <Card style={{ gap: 8 }}>
        <Text variant="subheading">All mistakes</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
          {STATUS_FILTERS.map(([value, label]) => (
            <Chip key={value} label={label} selected={status === value} onPress={() => filter(setStatus)(value)} />
          ))}
        </ScrollView>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
          <Chip label="All categories" selected={!category} onPress={() => filter(setCategory)("")} />
          {s.by_category.map((c) => (
            <Chip key={c.category} label={c.label} selected={category === c.category} onPress={() => filter(setCategory)(c.category)} />
          ))}
        </ScrollView>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
          <Chip label="All skills" selected={!source} onPress={() => filter(setSource)("")} />
          {SOURCES.map((src) => (
            <Chip key={src} label={titleCase(src)} selected={source === src} onPress={() => filter(setSource)(src)} />
          ))}
        </ScrollView>
        {list.isLoading ? (
          <ActivityIndicator />
        ) : list.error ? (
          <ErrorState error={list.error} onRetry={() => list.refetch()} />
        ) : list.data?.items.length ? (
          <>
            {list.data.items.map((m) => (
              <MistakeRow key={m.id} mistake={m} open={openId === m.id} onToggle={() => setOpenId(openId === m.id ? null : m.id)} />
            ))}
            {list.data.total > list.data.page_size ? (
              <Row style={{ justifyContent: "space-between", paddingTop: 8 }}>
                <Text variant="small" tone="muted">
                  Page {page} of {Math.ceil(list.data.total / list.data.page_size)}
                </Text>
                <Row>
                  <Button title="Previous" size="sm" variant="outline" disabled={page === 1} onPress={() => setPage((p) => p - 1)} />
                  <Button title="Next" size="sm" variant="outline" disabled={page * list.data.page_size >= list.data.total} onPress={() => setPage((p) => p + 1)} />
                </Row>
              </Row>
            ) : null}
          </>
        ) : (
          <EmptyState title="Nothing matches these filters" />
        )}
      </Card>
    </Screen>
  );
}
