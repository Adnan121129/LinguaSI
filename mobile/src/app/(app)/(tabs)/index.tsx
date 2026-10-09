import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { Brain, CalendarDays, Flame, GraduationCap, Sparkles, TrendingDown, TrendingUp, Zap } from "lucide-react-native";
import { View } from "react-native";

import { BandValue, OFFICIAL_DISCLAIMER } from "@/components/band";
import { BarList, ChartCard, ColumnChart } from "@/components/charts";
import { FocusAreas, MissionCard, RecommendationCard, SIFeed } from "@/components/learning-cards";
import { Logo } from "@/components/logo";
import { Button, Card, EmptyState, ErrorState, Loading, Notice, ProgressBar, Row, Screen, Stat, Text } from "@/components/ui";
import { useRefetchOnFocus } from "@/hooks/use-refetch-on-focus";
import { api } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import type { Dashboard } from "@/lib/types";
import { formatBand } from "@/lib/utils";

export default function HomeScreen() {
  const { colors } = useTheme();
  const { data, error, isLoading, refetch, isRefetching } = useQuery({ queryKey: ["dashboard"], queryFn: () => api<Dashboard>("/dashboard") });
  useRefetchOnFocus(refetch);

  if (isLoading) return <Loading label="Preparing your plan…" />;
  if (error || !data)
    return (
      <Screen safeTop>
        <ErrorState error={error} onRetry={() => refetch()} />
      </Screen>
    );

  const ielts = data.goal === "ielts";
  const weeklyGoal = data.weekly_goal_minutes || 1;
  const others = data.recommendations.filter((r) => r.id !== data.recommendation?.id).slice(0, 3);

  return (
    <Screen safeTop refreshing={isRefetching} onRefresh={refetch}>
      <Row style={{ justifyContent: "space-between" }}>
        <Logo size={30} />
        {data.ai.mock_mode ? <Text variant="caption" tone="warning" weight="600">Mock AI Mode</Text> : null}
      </Row>
      <View style={{ gap: 4 }}>
        <Text variant="title">{data.greeting}</Text>
        <Text tone="muted">
          {data.goal_label}
          {data.days_to_test !== null && data.days_to_test >= 0 ? ` · ${data.days_to_test} days to your test` : ""}
        </Text>
      </View>

      {!data.diagnostic_completed ? (
        <Card tone="primary">
          <Row>
            <GraduationCap size={18} color={colors.primary} />
            <Text weight="600" style={{ flex: 1 }}>Take the 15-minute diagnostic</Text>
          </Row>
          <Text variant="small">SI estimates your level from it and plans the right practice.</Text>
          <Button title="Start diagnostic" size="sm" onPress={() => router.push("/diagnostic")} style={{ alignSelf: "flex-start" }} />
        </Card>
      ) : null}

      <View style={{ flexDirection: "row", gap: 12 }}>
        <Card style={{ flex: 1 }}>
          {ielts ? (
            <>
              <BandValue band={data.estimated_band} target={data.target_band} />
              <Text variant="caption" tone="muted">Target {formatBand(data.target_band)} · {data.cefr ?? "—"}</Text>
              <ProgressBar value={((data.estimated_band ?? 0) / data.target_band) * 100} label="Progress to target band" />
            </>
          ) : (
            <>
              <Text variant="label" tone="muted">AI Estimated Level</Text>
              <Text style={{ fontSize: 30, fontWeight: "700" }}>{data.cefr ?? "—"}</Text>
              <Text variant="caption" tone="muted">CEFR estimate from recent practice</Text>
            </>
          )}
        </Card>
        <Card style={{ flex: 1 }}>
          <Row gap={6}>
            <Flame size={14} color={data.streak.current ? colors.danger : colors.mutedForeground} />
            <Text variant="label" tone="muted">Streak</Text>
          </Row>
          <Text style={{ fontSize: 30, fontWeight: "700" }}>
            {data.streak.current} <Text tone="muted">days</Text>
          </Text>
          <Text variant="caption" tone="muted">
            {data.streak.active_today ? "Done for today — nice." : data.streak.at_risk ? "Practise today to keep it." : "Start a streak today."} Best {data.streak.longest}.
          </Text>
        </Card>
      </View>

      <Card>
        <Row style={{ justifyContent: "space-between" }}>
          <Row gap={6}>
            <Zap size={14} color={colors.primary} />
            <Text variant="label" tone="muted">Level {data.level.level} · {data.level.title}</Text>
          </Row>
          <Text variant="caption" tone="muted">+{data.today_xp} XP today</Text>
        </Row>
        <ProgressBar value={data.level.progress * 100} label="Progress to next level" />
        <Text variant="caption" tone="muted">
          {data.level.xp.toLocaleString()} XP · {Math.max(0, data.level.next_level_xp - data.level.xp).toLocaleString()} to next level
        </Text>
      </Card>

      {data.recommendation ? <RecommendationCard rec={data.recommendation} primary /> : null}
      {data.mission ? <MissionCard mission={data.mission} /> : <EmptyState title="No mission yet" description="Your daily mission appears once SI knows a little about you." />}

      {data.insight ? (
        <Card>
          <Row>
            <Brain size={16} color={colors.primary} />
            <Text variant="subheading">Learning insight</Text>
          </Row>
          <Text variant="small" tone="muted">{data.insight.headline}</Text>
          {data.insight.weakness ? (
            <Text variant="small">
              <Text variant="small" weight="600">{data.insight.weakness}</Text> {data.insight.weakness_reason}
            </Text>
          ) : null}
          {data.insight.suggestion ? <Text variant="small" tone="primary">{data.insight.suggestion}</Text> : null}
        </Card>
      ) : null}

      <ChartCard
        question="Did I study enough this week?"
        description={`Minutes per day · dashed line: your ${Math.round(weeklyGoal / 7)}-minute daily goal`}
        rows={data.weekly}
        columns={[
          { key: "label", label: "Day" },
          { key: "minutes", label: "Minutes" },
          { key: "xp", label: "XP" },
        ]}
      >
        <ColumnChart data={data.weekly} xKey="label" yKey="minutes" unit=" min" reference={Math.round(weeklyGoal / 7)} label="Study minutes" />
        <Row style={{ justifyContent: "space-between" }}>
          <Row gap={6}>
            <CalendarDays size={14} color={colors.mutedForeground} />
            <Text variant="small" tone="muted">This week</Text>
          </Row>
          <Text variant="small" weight="600">
            {data.weekly_minutes} / {weeklyGoal} min
          </Text>
        </Row>
      </ChartCard>

      <Card>
        <Row style={{ justifyContent: "space-between" }}>
          <Text variant="subheading">Skills overview</Text>
          <Button title="Progress" size="sm" variant="ghost" onPress={() => router.push("/progress")} />
        </Row>
        <Text variant="caption" tone="muted">AI estimated scores (0–100) from recent practice, with the current difficulty level.</Text>
        <BarList
          rows={data.skills.map((s) => ({
            label: `${s.label}${s.trend === "improving" ? " ↑" : s.trend === "declining" ? " ↓" : ""}`,
            value: s.attempts ? s.score ?? 0 : null,
            note: `${s.band !== null ? `band ${formatBand(s.band)} · ` : ""}L${s.difficulty}`,
          }))}
        />
        <Row gap={14}>
          <Row gap={4}>
            <TrendingUp size={13} color={colors.success} />
            <Text variant="caption" tone="muted">↑ improving</Text>
          </Row>
          <Row gap={4}>
            <TrendingDown size={13} color={colors.danger} />
            <Text variant="caption" tone="muted">↓ declining</Text>
          </Row>
        </Row>
      </Card>

      <Card onPress={() => router.push("/vocabulary")}>
        <Text variant="subheading">Vocabulary</Text>
        <Row style={{ justifyContent: "space-between" }}>
          <Stat label="Known" value={data.vocabulary.known} />
          <Stat label="Mastered" value={data.vocabulary.mastered} />
          <Stat label="Due now" value={data.vocabulary.due} />
        </Row>
      </Card>

      <FocusAreas areas={data.weaknesses} />

      <Card>
        <Row>
          <Sparkles size={16} color={colors.primary} />
          <Text variant="subheading">What SI changed</Text>
        </Row>
        <SIFeed events={data.si_feed.slice(0, 4)} />
      </Card>

      {others.length ? (
        <View style={{ gap: 12 }}>
          <Text variant="small" tone="muted" weight="600">More recommendations</Text>
          {others.map((rec) => (
            <RecommendationCard key={rec.id} rec={rec} />
          ))}
        </View>
      ) : null}

      {ielts ? <Notice tone="muted">{OFFICIAL_DISCLAIMER}</Notice> : null}
    </Screen>
  );
}
