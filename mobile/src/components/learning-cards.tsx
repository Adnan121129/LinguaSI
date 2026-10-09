import { useMutation, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { ArrowRight, Check, ChevronDown, ChevronUp, CircleCheck, Clock, Lightbulb, Sparkles, Target, X, Zap } from "lucide-react-native";
import { useState } from "react";
import { Pressable, View } from "react-native";

import { Badge, Button, Card, CardHeader, ProgressBar, Row, Text } from "@/components/ui";
import { api } from "@/lib/api";
import { appHref } from "@/lib/routes";
import { useTheme } from "@/lib/theme";
import type { Mission, Recommendation, SIEvent } from "@/lib/types";
import { relativeTime } from "@/lib/utils";

export function MissionCard({ mission }: { mission: Mission }) {
  const { colors } = useTheme();
  return (
    <Card>
      <CardHeader title={mission.title} subtitle={mission.summary} action={<Badge tone={mission.status === "completed" ? "success" : "primary"} label={`${mission.completed_tasks}/${mission.total_tasks} done`} />} />
      {mission.tasks.map((task) => (
        <View key={task.id} style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 14, padding: 12, gap: 8, backgroundColor: task.completed ? colors.successSoft : "transparent" }}>
          <Row style={{ alignItems: "flex-start" }} gap={10}>
            <View
              style={{
                width: 20,
                height: 20,
                borderRadius: 10,
                borderWidth: 1,
                marginTop: 1,
                borderColor: task.completed ? colors.success : colors.border,
                backgroundColor: task.completed ? colors.success : "transparent",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {task.completed ? <Check size={12} color="#ffffff" /> : null}
            </View>
            <View style={{ flex: 1, gap: 4 }}>
              <Text weight="600" tone={task.completed ? "muted" : "default"} style={task.completed ? { textDecorationLine: "line-through" } : undefined}>
                {task.title}
              </Text>
              <Row gap={10}>
                <Row gap={4}>
                  <Clock size={12} color={colors.mutedForeground} />
                  <Text variant="caption" tone="muted">{task.minutes} min</Text>
                </Row>
                <Row gap={4}>
                  <Zap size={12} color={colors.mutedForeground} />
                  <Text variant="caption" tone="muted">{task.xp} XP</Text>
                </Row>
              </Row>
              <Text variant="small" tone="muted">{task.why}</Text>
              {task.target > 1 ? <ProgressBar value={(task.progress / task.target) * 100} tone={task.completed ? "success" : "primary"} height={6} label={`${task.title} progress`} /> : null}
            </View>
          </Row>
          {!task.completed ? <Button title="Start" size="sm" variant="secondary" onPress={() => router.push(appHref(task.route))} accessibilityLabel={`Start: ${task.title}`} style={{ alignSelf: "flex-start" }} /> : null}
        </View>
      ))}
      {mission.status === "completed" ? (
        <Row>
          <CircleCheck size={16} color={colors.success} />
          <Text variant="small" tone="success" weight="600">Mission complete — {mission.bonus_xp} bonus XP earned.</Text>
        </Row>
      ) : (
        <Text variant="caption" tone="muted">Finish every task for {mission.bonus_xp} bonus XP.</Text>
      )}
    </Card>
  );
}

export function RecommendationCard({ rec, primary = false }: { rec: Recommendation; primary?: boolean }) {
  const { colors } = useTheme();
  const [open, setOpen] = useState(primary);
  const queryClient = useQueryClient();
  const dismiss = useMutation({
    mutationFn: () => api(`/recommendations/${rec.id}/dismiss`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });
  return (
    <Card tone={primary ? "primary" : undefined} style={primary ? { borderColor: colors.primary + "55" } : undefined}>
      <Row style={{ alignItems: "flex-start" }}>
        <View style={{ flex: 1, gap: 4 }}>
          {primary ? (
            <Row gap={6}>
              <Sparkles size={13} color={colors.primary} />
              <Text variant="label" tone="primary">SI recommends</Text>
            </Row>
          ) : null}
          <Text weight="600">{rec.title}</Text>
          <Text variant="small" tone="muted">{rec.description}</Text>
        </View>
        <Pressable onPress={() => dismiss.mutate()} disabled={dismiss.isPending} hitSlop={10} accessibilityRole="button" accessibilityLabel={`Dismiss recommendation: ${rec.title}`}>
          <X size={18} color={colors.mutedForeground} />
        </Pressable>
      </Row>
      <Pressable onPress={() => setOpen((o) => !o)} accessibilityRole="button" accessibilityState={{ expanded: open }} style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
        <Lightbulb size={15} color={colors.primary} />
        <Text variant="small" tone="primary" weight="600">Why this?</Text>
        {open ? <ChevronUp size={15} color={colors.primary} /> : <ChevronDown size={15} color={colors.primary} />}
      </Pressable>
      {open ? (
        <View style={{ backgroundColor: colors.card, borderRadius: 12, padding: 12 }}>
          <Text variant="small">{rec.why}</Text>
        </View>
      ) : null}
      <Row gap={12}>
        {rec.route ? <Button title="Start" icon={ArrowRight} size="sm" variant={primary ? "primary" : "secondary"} onPress={() => router.push(appHref(rec.route))} accessibilityLabel={`Start: ${rec.title}`} /> : null}
        <Text variant="caption" tone="muted">About {rec.estimated_minutes} min</Text>
      </Row>
    </Card>
  );
}

export function SIFeed({ events }: { events: SIEvent[] }) {
  const { colors } = useTheme();
  if (!events.length) return <Text variant="small" tone="muted">SI will explain what it changes after your first activity.</Text>;
  return (
    <View style={{ gap: 14 }}>
      {events.map((event) => (
        <View key={event.id} style={{ flexDirection: "row", gap: 10 }}>
          <View style={{ width: 8, height: 8, borderRadius: 4, marginTop: 6, backgroundColor: colors.primary }} />
          <View style={{ flex: 1, gap: 2 }}>
            <Text variant="small" weight="600">{event.title}</Text>
            <Text variant="small" tone="muted">{event.detail}</Text>
            {event.actions.slice(0, 3).map((action) => (
              <Text key={action} variant="caption" tone="muted">→ {action}</Text>
            ))}
            <Text variant="caption" tone="muted">{relativeTime(event.created_at)}</Text>
          </View>
        </View>
      ))}
    </View>
  );
}

export function FocusAreas({ areas }: { areas: { key: string; label: string; reason: string }[] }) {
  const { colors } = useTheme();
  if (!areas.length) return null;
  return (
    <Card>
      <Row>
        <Target size={16} color={colors.primary} />
        <Text variant="subheading">Focus areas</Text>
      </Row>
      {areas.map((area) => (
        <View key={area.key} style={{ gap: 2 }}>
          <Text weight="600">{area.label}</Text>
          <Text variant="small" tone="muted">{area.reason}</Text>
        </View>
      ))}
      <Button title="Open My Mistakes" variant="outline" size="sm" icon={ArrowRight} onPress={() => router.push("/mistakes")} />
    </Card>
  );
}
