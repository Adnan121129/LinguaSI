import { useMutation, useQuery } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator } from "react-native";

import { AttemptHistory, AttemptSetup, READING_TYPES, type SetupValues } from "@/components/comprehension";
import { useToast } from "@/components/toast";
import { Card, EmptyState, ErrorState, Screen, Text } from "@/components/ui";
import { useRefetchOnFocus } from "@/hooks/use-refetch-on-focus";
import { api, errorMessage } from "@/lib/api";
import type { AttemptSummary, Page, ReadingAttempt } from "@/lib/types";

export default function ReadingHub() {
  const params = useLocalSearchParams<{ types?: string; difficulty?: string }>();
  const { push } = useToast();
  const history = useQuery({ queryKey: ["reading-history"], queryFn: () => api<Page<AttemptSummary>>("/reading/history?page_size=20") });
  useRefetchOnFocus(history.refetch);
  const start = useMutation({
    mutationFn: (v: SetupValues) =>
      api<ReadingAttempt>("/reading/generate", {
        json: { difficulty: v.difficulty, topic: v.topic.trim() || null, question_count: v.question_count, time_limit_minutes: v.time_limit_minutes, question_types: v.question_types.length ? v.question_types : null },
      }),
    onSuccess: (attempt) => router.push(`/reading/${attempt.id}`),
    onError: (err) => push({ tone: "error", title: "Couldn't create a reading set", description: errorMessage(err) }),
  });
  const types = params.types?.split(",").filter((t) => READING_TYPES.includes(t)) ?? [];
  return (
    <Screen refreshing={history.isRefetching} onRefresh={history.refetch}>
      <Text tone="muted">Original passages at your level with IELTS-style question types. Every answer comes with the evidence from the text.</Text>
      <AttemptSetup types={READING_TYPES} defaults={{ difficulty: Number(params.difficulty) || null, types }} onStart={(v) => start.mutate(v)} starting={start.isPending} defaultCount={8} defaultMinutes={20} />
      <Card style={{ gap: 0, paddingVertical: 4 }}>
        <Text variant="subheading" style={{ paddingTop: 10 }}>Recent reading</Text>
        {history.isLoading ? (
          <ActivityIndicator />
        ) : history.error ? (
          <ErrorState error={history.error} onRetry={() => history.refetch()} />
        ) : history.data?.items.length ? (
          <AttemptHistory items={history.data.items} base="/reading" />
        ) : (
          <EmptyState title="No reading practice yet" description="Your results and estimated reading band will appear here." />
        )}
      </Card>
    </Screen>
  );
}
