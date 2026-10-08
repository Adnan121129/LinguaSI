"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { AttemptHistory, LISTENING_TYPES } from "@/components/comprehension/attempt-history";
import { AttemptSetup, type SetupValues } from "@/components/comprehension/attempt-setup";
import { useToast } from "@/components/providers/toast";
import { Card, CardBody, CardHeader, EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { AttemptSummary, ListeningAttempt, Page } from "@/lib/types";

function ListeningHub() {
  const params = useSearchParams();
  const router = useRouter();
  const { push } = useToast();
  const history = useQuery({ queryKey: ["listening-history"], queryFn: () => api<Page<AttemptSummary>>("/listening/history?page_size=20") });
  const start = useMutation({
    mutationFn: (v: SetupValues) =>
      api<ListeningAttempt>("/listening/generate", {
        json: {
          difficulty: v.difficulty,
          topic: v.topic || null,
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
  const types = params.get("types")?.split(",").filter((t) => LISTENING_TYPES.includes(t)) ?? [];
  return (
    <div className="space-y-6">
      <PageHeader title="Listening" description="Original conversations, talks and lectures at your level. Audio uses studio voices when configured, otherwise your device's voices." />
      <AttemptSetup
        types={LISTENING_TYPES}
        defaults={{ difficulty: Number(params.get("difficulty")) || null, types }}
        extraFields={[
          {
            key: "scenario",
            label: "Recording type",
            options: [
              ["", "Any"],
              ["conversation", "Conversation"],
              ["monologue", "Talk / announcement"],
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
      <Card>
        <CardHeader title="Recent listening" />
        <CardBody>
          {history.isLoading ? (
            <Skeleton className="h-32" />
          ) : history.error ? (
            <ErrorState error={history.error} onRetry={() => history.refetch()} />
          ) : history.data?.items.length ? (
            <AttemptHistory items={history.data.items} base="/listening" />
          ) : (
            <EmptyState title="No listening practice yet" description="Your results and estimated listening band will appear here." />
          )}
        </CardBody>
      </Card>
    </div>
  );
}

export default function ListeningPage() {
  return (
    <Suspense>
      <ListeningHub />
    </Suspense>
  );
}
