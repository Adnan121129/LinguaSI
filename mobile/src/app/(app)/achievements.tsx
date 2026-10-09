import { useQuery } from "@tanstack/react-query";
import {
  AudioLines,
  Award,
  Blocks,
  BookOpen,
  BookOpenCheck,
  Crown,
  Flag,
  Flame,
  Hammer,
  Headphones,
  Library,
  Lock,
  Medal,
  MessageCircleQuestion,
  Mic,
  Mountain,
  NotebookPen,
  Orbit,
  PenLine,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  Trophy,
  type LucideIcon,
} from "lucide-react-native";
import { View } from "react-native";

import { MissionCard } from "@/components/learning-cards";
import { Badge, Card, ErrorState, Loading, ProgressBar, Row, Screen, Stat, Text, type Tone } from "@/components/ui";
import { api } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import type { AchievementsResponse, MissionsResponse } from "@/lib/types";
import { formatDate, relativeTime } from "@/lib/utils";

// Icon names come from the achievements seed file.
const ICONS: Record<string, LucideIcon> = {
  "audio-lines": AudioLines,
  blocks: Blocks,
  "book-open": BookOpen,
  "book-open-check": BookOpenCheck,
  crown: Crown,
  flag: Flag,
  flame: Flame,
  hammer: Hammer,
  headphones: Headphones,
  library: Library,
  medal: Medal,
  "message-circle-question": MessageCircleQuestion,
  mic: Mic,
  mountain: Mountain,
  "notebook-pen": NotebookPen,
  orbit: Orbit,
  "pen-line": PenLine,
  "shield-check": ShieldCheck,
  sparkles: Sparkles,
  target: Target,
  "trending-up": TrendingUp,
  trophy: Trophy,
};
const TIER_TONE: Record<string, Tone> = { bronze: "warning", silver: "muted", gold: "primary" };

export default function AchievementsScreen() {
  const { colors } = useTheme();
  const achievements = useQuery({ queryKey: ["achievements"], queryFn: () => api<AchievementsResponse>("/achievements") });
  const missions = useQuery({ queryKey: ["missions"], queryFn: () => api<MissionsResponse>("/missions") });
  if (achievements.isLoading || missions.isLoading) return <Loading />;
  if (achievements.error || !achievements.data)
    return (
      <Screen>
        <ErrorState error={achievements.error} onRetry={() => achievements.refetch()} />
      </Screen>
    );
  const a = achievements.data;
  const earned = a.achievements.filter((x) => x.earned).length;
  return (
    <Screen
      refreshing={achievements.isRefetching}
      onRefresh={() => {
        achievements.refetch();
        missions.refetch();
      }}
    >
      <Card>
        <Text variant="label" tone="muted">Level {a.level.level}</Text>
        <Text variant="heading">{a.level.title}</Text>
        <ProgressBar value={a.level.progress * 100} label="Progress to next level" />
        <Text variant="caption" tone="muted">
          {a.level.xp.toLocaleString()} XP · {(a.level.next_level_xp - a.level.xp).toLocaleString()} XP to level {a.level.level + 1}
        </Text>
      </Card>
      <Row style={{ gap: 12 }}>
        <Card style={{ flex: 1 }}>
          <Row gap={6}>
            <Flame size={15} color={colors.danger} />
            <Text variant="label" tone="muted">Streak</Text>
          </Row>
          <Text variant="heading">{a.streak.current} day{a.streak.current === 1 ? "" : "s"}</Text>
          <Text variant="caption" tone="muted">
            Longest {a.streak.longest} · {a.streak.freezes} freeze{a.streak.freezes === 1 ? "" : "s"} (one earned every 7 days)
          </Text>
        </Card>
        <Card style={{ flex: 1 }}>
          <Stat label="Badges" value={`${earned} / ${a.achievements.length}`} />
        </Card>
      </Row>
      {missions.data?.today ? <MissionCard mission={missions.data.today} /> : null}
      {missions.data?.challenges.length ? (
        <Card>
          <Text variant="subheading">This week&apos;s challenges</Text>
          <Text variant="caption" tone="muted">Weekly goals tuned to your weakest skill.</Text>
          {missions.data.challenges.map((c) => (
            <View key={c.id} style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 14, padding: 12, gap: 6, backgroundColor: c.completed ? colors.successSoft : "transparent" }}>
              <Row style={{ justifyContent: "space-between" }}>
                <Text weight="600" style={{ flex: 1 }}>{c.title}</Text>
                <Badge tone={c.completed ? "success" : "primary"} label={`+${c.xp_reward} XP`} />
              </Row>
              <Text variant="small" tone="muted">{c.description}</Text>
              <ProgressBar value={(c.progress / c.target) * 100} tone={c.completed ? "success" : "primary"} label={c.title} />
              <Text variant="caption" tone="muted">
                {Math.min(c.progress, c.target)} / {c.target}
              </Text>
            </View>
          ))}
        </Card>
      ) : null}
      <Card>
        <Text variant="subheading">Badges</Text>
        {a.achievements.map((x) => {
          const Icon = ICONS[x.icon] ?? Award;
          return (
            <Row key={x.code} gap={12} style={{ alignItems: "flex-start", opacity: x.earned ? 1 : 0.8 }}>
              <View style={{ width: 44, height: 44, borderRadius: 12, alignItems: "center", justifyContent: "center", backgroundColor: x.earned ? colors.warningSoft : colors.muted }}>
                {x.earned ? <Icon size={20} color={colors.warning} /> : <Lock size={17} color={colors.mutedForeground} />}
              </View>
              <View style={{ flex: 1, gap: 3 }}>
                <Row gap={6}>
                  <Text weight="600">{x.name}</Text>
                  <Badge tone={TIER_TONE[x.tier] ?? "muted"} label={x.tier} />
                </Row>
                <Text variant="caption" tone="muted">{x.description}</Text>
                {x.earned ? <Text variant="caption" tone="success">Earned {formatDate(x.earned_at)}</Text> : <ProgressBar value={x.progress * 100} height={6} label={`${x.name} progress`} />}
              </View>
            </Row>
          );
        })}
      </Card>
      <Card>
        <Text variant="subheading">Recent XP</Text>
        {a.recent_xp.map((x, i) => (
          <Row key={i} style={{ justifyContent: "space-between" }}>
            <Text variant="small" numberOfLines={1} style={{ flex: 1 }}>{x.description || x.reason}</Text>
            <Text variant="small" tone="muted">
              <Text variant="small" weight="700" tone="primary">+{x.amount}</Text> · {relativeTime(x.created_at)}
            </Text>
          </Row>
        ))}
      </Card>
      {missions.data?.history.length ? (
        <Card>
          <Text variant="subheading">Mission history</Text>
          {missions.data.history.map((m) => (
            <Row key={m.day} style={{ justifyContent: "space-between" }}>
              <Text variant="small">{formatDate(m.day)}</Text>
              <Badge tone={m.status === "completed" ? "success" : "muted"} label={`${m.completed_tasks}/${m.total_tasks} tasks`} />
            </Row>
          ))}
        </Card>
      ) : null}
    </Screen>
  );
}
