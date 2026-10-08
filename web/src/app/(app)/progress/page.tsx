"use client";

import { useQuery } from "@tanstack/react-query";
import { Lightbulb, TrendingDown, TrendingUp } from "lucide-react";
import { useState } from "react";

import { BandValue } from "@/components/band";
import { CalendarHeatmap, ChartCard, ColumnChart, MultiLineChart, SERIES_COLORS, SkillBars, shortDay, shortWeek } from "@/components/charts";
import { Card, CardBody, CardHeader, ErrorState, PageHeader, PageSkeleton, Stat, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import type { Progress } from "@/lib/types";

const BAND_SERIES = [
  { key: "overall", label: "Overall", color: SERIES_COLORS.overall },
  { key: "reading", label: "Reading", color: SERIES_COLORS.reading },
  { key: "listening", label: "Listening", color: SERIES_COLORS.listening },
  { key: "writing", label: "Writing", color: SERIES_COLORS.writing },
  { key: "speaking", label: "Speaking", color: SERIES_COLORS.speaking },
];
const WEEKLY_SERIES = [
  { key: "writing", label: "Writing", color: SERIES_COLORS.writing },
  { key: "speaking", label: "Speaking", color: SERIES_COLORS.speaking },
  { key: "vocabulary", label: "Vocabulary", color: SERIES_COLORS.vocabulary },
];

function InsightList({ title, items, icon }: { title: string; items: string[]; icon: React.ReactNode }) {
  if (!items.length) return null;
  return (
    <div>
      <p className="flex items-center gap-1.5 text-sm font-semibold">
        {icon} {title}
      </p>
      <ul className="mt-1.5 space-y-1 text-sm text-muted-foreground">{items.map((i) => <li key={i}>{i}</li>)}</ul>
    </div>
  );
}

export default function ProgressPage() {
  const [days, setDays] = useState<"30" | "90" | "180">("30");
  const { data, error, isLoading, refetch } = useQuery({ queryKey: ["progress", days], queryFn: () => api<Progress>(`/progress?days=${days}`) });
  if (isLoading) return <PageSkeleton />;
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />;
  const q = data.chart_questions;
  const target = data.target_band;
  return (
    <div className="space-y-6">
      <PageHeader
        title="Progress"
        description="Every chart answers one question about your learning."
        action={
          <Tabs
            value={days}
            onChange={setDays}
            items={[
              { value: "30", label: "30 days" },
              { value: "90", label: "90 days" },
              { value: "180", label: "6 months" },
            ]}
          />
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardBody className="space-y-4">
            <BandValue band={data.estimated_band} size="xl" target={target} />
            <p className="text-sm text-muted-foreground">
              Target {target.toFixed(1)} · {data.cefr ?? "—"} level
            </p>
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Sessions" value={data.totals.sessions} />
              <Stat label="Minutes" value={data.totals.minutes} />
              <Stat label="Active days" value={data.totals.active_days} />
              <Stat label="XP earned" value={data.totals.xp.toLocaleString()} />
            </div>
          </CardBody>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader icon={<Lightbulb className="size-4" />} title="What changed" description={data.insights.headline} />
          <CardBody className="grid gap-4 sm:grid-cols-2">
            <InsightList title="Improvements" items={data.insights.improvements} icon={<TrendingUp className="size-4 text-success" aria-hidden />} />
            <InsightList title="Needs attention" items={[...data.insights.regressions, ...data.insights.skill_gaps]} icon={<TrendingDown className="size-4 text-warning" aria-hidden />} />
            <InsightList title="Recurring weaknesses" items={data.insights.recurring_weaknesses} icon={<span className="size-2 rounded-full bg-danger" aria-hidden />} />
            <div className="rounded-xl bg-primary-soft/60 p-3 text-sm sm:col-span-2">
              <span className="font-semibold text-primary">Next focus: </span>
              {data.insights.next_focus}
            </div>
          </CardBody>
        </Card>
      </div>

      <ChartCard
        question={q.band_history}
        description="AI estimated bands over time (practice indicators, not official scores)"
        rows={data.band_history}
        columns={[{ key: "day", label: "Day" }, ...BAND_SERIES.map((s) => ({ key: s.key, label: s.label }))]}
        legend={BAND_SERIES}
      >
        <MultiLineChart data={data.band_history} xKey="day" xFormat={shortDay} series={BAND_SERIES} yDomain={[3, 9]} reference={{ value: target, label: `Target ${target.toFixed(1)}` }} height={280} />
      </ChartCard>

      <div className="grid gap-6 lg:grid-cols-2">
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
          <SkillBars rows={data.skills_radar.map((s) => ({ label: s.label, score: s.score, target: s.target }))} />
        </ChartCard>
        <ChartCard
          question={q.weekly_scores}
          description="Average weekly scores (0–100)"
          rows={data.weekly_scores}
          columns={[{ key: "week", label: "Week" }, ...WEEKLY_SERIES.map((s) => ({ key: s.key, label: s.label }))]}
          legend={WEEKLY_SERIES}
        >
          <MultiLineChart data={data.weekly_scores} xKey="week" xFormat={shortWeek} series={WEEKLY_SERIES} yDomain={[0, 100]} />
        </ChartCard>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard
          question={q.vocabulary_growth}
          description="Words you know and words mastered"
          rows={data.vocabulary_growth}
          columns={[
            { key: "day", label: "Day" },
            { key: "known", label: "Known" },
            { key: "mastered", label: "Mastered" },
          ]}
          legend={[
            { label: "Known", color: SERIES_COLORS.known },
            { label: "Mastered", color: SERIES_COLORS.mastered },
          ]}
        >
          <MultiLineChart
            data={data.vocabulary_growth}
            xKey="day"
            xFormat={shortDay}
            series={[
              { key: "known", label: "Known", color: SERIES_COLORS.known },
              { key: "mastered", label: "Mastered", color: SERIES_COLORS.mastered },
            ]}
          />
        </ChartCard>
        <ChartCard
          question={q.mistake_reduction}
          description="Writing and speaking errors per 100 words, by week (lower is better)"
          rows={data.mistake_reduction}
          columns={[
            { key: "week", label: "Week" },
            { key: "errors", label: "Errors" },
            { key: "words", label: "Words" },
            { key: "per_100_words", label: "Per 100 words" },
          ]}
        >
          <ColumnChart data={data.mistake_reduction} xKey="week" yKey="per_100_words" label="Errors per 100 words" xFormat={shortWeek} />
        </ChartCard>
      </div>

      <ChartCard
        question={q.consistency}
        description="Minutes studied each day"
        rows={data.consistency}
        columns={[
          { key: "day", label: "Day" },
          { key: "minutes", label: "Minutes" },
          { key: "xp", label: "XP" },
        ]}
      >
        <CalendarHeatmap days={data.consistency} />
      </ChartCard>
    </div>
  );
}
