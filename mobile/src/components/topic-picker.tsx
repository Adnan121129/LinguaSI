import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { BookMarked, Puzzle } from "lucide-react-native";
import { useState } from "react";
import { ActivityIndicator } from "react-native";

import { Button, Card, ErrorState, Row, Text } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { appHref } from "@/lib/routes";
import { useTheme } from "@/lib/theme";
import type { PracticeSet } from "@/lib/types";

type Topic = { focus: string; label: string; items: number; guide: string | null };

/** Build a set for a focus area and open it. Question types and fluency are practised inside their skill instead. */
export async function openPractice(focus: string, { from, replace = false }: { from?: string; replace?: boolean } = {}) {
  const go = replace ? router.replace : router.push;
  try {
    const practice = await api<PracticeSet>("/practice/sets", { json: { focus, item_count: 8 } });
    go(from ? `/practice/${practice.id}?from=${from}` : `/practice/${practice.id}`);
  } catch (err) {
    if (err instanceof ApiError && err.code === "use_skill_practice") {
      go(appHref((err.details as { route: string }).route));
      return;
    }
    throw err;
  }
}

/** Grammar and language-area picker that builds a practice set and opens it. */
export function TopicPicker({ from }: { from?: string }) {
  const { colors } = useTheme();
  const [creating, setCreating] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const topics = useQuery({ queryKey: ["practice-topics"], queryFn: () => api<Topic[]>("/practice/topics") });

  async function create(topic: string) {
    setCreating(topic);
    setError(null);
    try {
      await openPractice(topic, { from });
    } catch (err) {
      setError(err);
    } finally {
      setCreating(null);
    }
  }

  if (topics.isLoading) return <ActivityIndicator color={colors.primary} />;
  if (topics.error) return <ErrorState error={topics.error} onRetry={() => topics.refetch()} />;
  return (
    <>
      {error ? <ErrorState error={error} /> : null}
      {topics.data?.map((t) => (
        <Card key={t.focus}>
          <Row>
            <Puzzle size={16} color={colors.primary} />
            <Text weight="600" style={{ flex: 1 }}>{t.label}</Text>
          </Row>
          {t.guide ? <Text variant="small" tone="muted" numberOfLines={3}>{t.guide}</Text> : null}
          <Row>
            <BookMarked size={13} color={colors.mutedForeground} />
            <Text variant="caption" tone="muted">{t.items} exercises in the bank</Text>
          </Row>
          <Button title="Practise" size="sm" variant="secondary" loading={creating === t.focus} disabled={!!creating} onPress={() => create(t.focus)} style={{ alignSelf: "flex-start" }} />
        </Card>
      ))}
    </>
  );
}
