import { useQuery } from "@tanstack/react-query";
import { Lightbulb, TrendingDown, TrendingUp, type LucideIcon } from "lucide-react-native";
import { useState } from "react";
import { View } from "react-native";

import { BandValue } from "@/components/band";
import { BarList, CalendarGrid, ChartCard, ColumnChart, LineChart, shortDay, shortWeek } from "@/components/charts";
import { Card, Loading, ErrorState, Row, Screen, Segmented, Stat, StatGrid, Text } from "@/components/ui";
import { api } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import type { Progress } from "@/lib/types";

function InsightList({ title, items, icon: Icon, color }: { title: string; items: string[]; icon: LucideIcon; color: string }) {
  if (!items.length) return null;
  return (
    <View style={{ gap: 4 }}>
      <Row gap={6}>
        <Icon size={15} color={color} />
        <Text variant="small" weight="600">{title}</Text>
      </Row>
      {items.map((item) => (
        <Text key={item} variant="small" tone="muted">{item}</Text>
      ))}
    </View>
  );
}

export default function ProgressScreen() {
  const { colors } = useTheme();
  const [days, setDays] = useState<"30" | "90" | "180">("30");
  const { data, error, isLoading, refetch, isRefetching } = useQuery({ queryKey: ["progress", days], queryFn: () => api<Progress>(`/progress?days=${days}`) });
  if (isLoading) return <Loading />;
  if (error || !data)
    return (
      <Screen>
        <ErrorState error={error} onRetry={() => refetch()} />
      </Screen>
    );

  // Colour follows the skill in every chart (same fixed order as the web app).
  const bandSeries = [
    { key: "overall", label: "Overall", color: colors.series[0] },
    { key: "reading", label: "Reading", color: colors.series[1] },
    { key: "listening", label: "Listening", color: colors.series[2] },
    { key: "writing", label: "Writing", color: colors.series[3] },
    { key: "speaking", label: "Speaking", color: colors.series[4] },
  ];
  const weeklySeries = [
    { key: "writing", label: "Writing", color: colors.series[3] },
    { key: "speaking", label: "Speaking", color: colors.series[4] },
    { key: "vocabulary", label: "Vocabulary", color: colors.series[0] },
  ];
  const q = data.chart_questions;
  const target = data.target_band;

  return (
    <Screen refreshing={isRefetching} onRefresh={refetch}>
      <Text tone="muted">Every chart answers one question about your learning.</Text>
      <Segmented
        value={days}
        onChange={setDays}
        options={[
          { value: "30", label: "30 days" },
          { value: "90", label: "90 days" },
          { value: "180", label: "6 months" },
        ]}
      />
      <Card>
        <BandValue band={data.estimated_band} size="lg" target={target} />
        <Text variant="small" tone="muted">
          Target {target.toFixed(1)} · {data.cefr ?? "—"} level
        </Text>
        <StatGrid>
          <Stat label="Sessions" value={data.totals.sessions} />
          <Stat label="Minutes" value={data.totals.minutes} />
          <Stat label="Active days" value={data.totals.active_days} />
          <Stat label="XP earned" value={data.totals.xp.toLocaleString()} />
        </StatGrid>
      </Card>
      <Card>
        <Row>
          <Lightbulb size={16} color={colors.primary} />
          <Text variant="subheading">What changed</Text>
        </Row>
        <Text variant="small" tone="muted">{data.insights.headline}</Text>
        <InsightList title="Improvements" items={data.insights.improvements} icon={TrendingUp} color={colors.success} />
        <InsightList title="Needs attention" items={[...data.insights.regressions, ...data.insights.skill_gaps]} icon={TrendingDown} color={colors.warning} />
        <InsightList title="Recurring weaknesses" items={data.insights.recurring_weaknesses} icon={TrendingDown} color={colors.danger} />
        <View style={{ backgroundColor: colors.primarySoft, borderRadius: 12, padding: 10 }}>
          <Text variant="small">
            <Text variant="small" weight="700" tone="primary">Next focus: </Text>
            {data.insights.next_focus}
          </Text>
        </View>
      </Card>
      <ChartCard
        question={q.band_history}
        description="AI estimated bands over time (practice indicators, not official scores)"
        rows={data.band_history}
        columns={[{ key: "day", label: "Day", format: (v) => shortDay(String(v)) }, ...bandSeries.map((s) => ({ key: s.key, label: s.label }))]}
        legend={bandSeries}
      >
        <LineChart data={data.band_history} xKey="day" xFormat={shortDay} series={bandSeries} domain={[3, 9]} reference={{ value: target, label: `Target ${target.toFixed(1)}` }} height={220} />
      </ChartCard>
      <ChartCard
        question={q.skills_radar}
        description="Current skill scores (0–100); the marker shows your target"
        rows={data.skills_radar}
        columns={[
          { key: "label", label: "Skill" },
          { key: "score", label: "Score", format: (v) => (v === null ? "—" : String(Math.round(Number(v)))) },
          { key: "target", label: "Target", format: (v) => String(Math.round(Number(v))) },
        ]}
      >
        <BarList rows={data.skills_radar.map((s) => ({ label: s.label, value: s.score, target: s.target }))} />
      </ChartCard>
      <ChartCard
        question={q.weekly_scores}
        description="Average weekly scores (0–100)"
        rows={data.weekly_scores}
        columns={[{ key: "week", label: "Week", format: (v) => shortWeek(String(v)) }, ...weeklySeries.map((s) => ({ key: s.key, label: s.label }))]}
        legend={weeklySeries}
      >
        <LineChart data={data.weekly_scores} xKey="week" xFormat={shortWeek} series={weeklySeries} domain={[0, 100]} />
      </ChartCard>
      <ChartCard
        question={q.vocabulary_growth}
        description="Words you know and words mastered"
        rows={data.vocabulary_growth}
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
          data={data.vocabulary_growth}
          xKey="day"
          xFormat={shortDay}
          series={[
            { key: "known", label: "Known", color: colors.series[0] },
            { key: "mastered", label: "Mastered", color: colors.series[2] },
          ]}
        />
      </ChartCard>
      <ChartCard
        question={q.mistake_reduction}
        description="Writing and speaking errors per 100 words, by week (lower is better)"
        rows={data.mistake_reduction}
        columns={[
          { key: "week", label: "Week", format: (v) => shortWeek(String(v)) },
          { key: "errors", label: "Errors" },
          { key: "words", label: "Words" },
          { key: "per_100_words", label: "Per 100" },
        ]}
      >
        <ColumnChart data={data.mistake_reduction} xKey="week" yKey="per_100_words" label="Errors per 100 words" xFormat={shortWeek} />
      </ChartCard>
      <ChartCard
        question={q.consistency}
        description="Minutes studied each day"
        rows={data.consistency}
        columns={[
          { key: "day", label: "Day", format: (v) => shortDay(String(v)) },
          { key: "minutes", label: "Minutes" },
          { key: "xp", label: "XP" },
        ]}
      >
        <CalendarGrid days={data.consistency} />
      </ChartCard>
    </Screen>
  );
}
