import { useMutation, useQuery } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator } from "react-native";

import { AttemptHistory, AttemptSetup, LISTENING_TYPES, type SetupValues } from "@/components/comprehension";
import { useToast } from "@/components/toast";
import { Card, EmptyState, ErrorState, Screen, Text } from "@/components/ui";
import { useRefetchOnFocus } from "@/hooks/use-refetch-on-focus";
import { api, errorMessage } from "@/lib/api";
import type { AttemptSummary, ListeningAttempt, Page } from "@/lib/types";

export default function ListeningHub() {
  const params = useLocalSearchParams<{ types?: string; difficulty?: string }>();
  const { push } = useToast();
  const history = useQuery({ queryKey: ["listening-history"], queryFn: () => api<Page<AttemptSummary>>("/listening/history?page_size=20") });
  useRefetchOnFocus(history.refetch);
  const start = useMutation({
    mutationFn: (v: SetupValues) =>
      api<ListeningAttempt>("/listening/generate", {
        json: {
          difficulty: v.difficulty,
          topic: v.topic.trim() || null,
          question_count: Math.min(v.question_count, 12),
          time_limit_minutes: Math.min(v.time_limit_minutes, 45),
          question_types: v.question_types.length ? v.question_types : null,
          scenario: v.extra.scenario || null,
          accent: v.extra.accent || null,
        },
      }),
    onSuccess: (attempt) => router.push(`/listening/${attempt.id}`),
    onError: (err) => push({ tone: "error", title: "Couldn't create a listening set", description: errorMessage(err) }),
  });
  const types = params.types?.split(",").filter((t) => LISTENING_TYPES.includes(t)) ?? [];
  return (
    <Screen refreshing={history.isRefetching} onRefresh={history.refetch}>
      <Text tone="muted">Original conversations, talks and lectures at your level. Audio uses studio voices when the server has them, otherwise your phone&apos;s voices.</Text>
      <AttemptSetup
        types={LISTENING_TYPES}
        defaults={{ difficulty: Number(params.difficulty) || null, types }}
        extraFields={[
          {
            key: "scenario",
            label: "Recording type",
            options: [
              ["", "Any"],
              ["conversation", "Conversation"],
              ["monologue", "Talk"],
              ["discussion", "Discussion"],
              ["lecture", "Lecture"],
            ],
          },
          {
            key: "accent",
            label: "Accent",
            options: [
              ["", "Any"],
              ["british", "British"],
              ["american", "American"],
              ["australian", "Australian"],
            ],
          },
        ]}
        onStart={(v) => start.mutate(v)}
        starting={start.isPending}
        defaultCount={6}
        defaultMinutes={15}
      />
      <Card style={{ gap: 0, paddingVertical: 4 }}>
        <Text variant="subheading" style={{ paddingTop: 10 }}>Recent listening</Text>
        {history.isLoading ? (
          <ActivityIndicator />
        ) : history.error ? (
          <ErrorState error={history.error} onRetry={() => history.refetch()} />
        ) : history.data?.items.length ? (
          <AttemptHistory items={history.data.items} base="/listening" />
        ) : (
          <EmptyState title="No listening practice yet" description="Your results and estimated listening band will appear here." />
        )}
      </Card>
    </Screen>
  );
}
