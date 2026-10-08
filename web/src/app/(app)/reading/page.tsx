"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { AttemptHistory, READING_TYPES } from "@/components/comprehension/attempt-history";
import { AttemptSetup, type SetupValues } from "@/components/comprehension/attempt-setup";
import { useToast } from "@/components/providers/toast";
import { Card, CardBody, CardHeader, EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { AttemptSummary, Page, ReadingAttempt } from "@/lib/types";

function ReadingHub() {
  const params = useSearchParams();
  const router = useRouter();
  const { push } = useToast();
  const history = useQuery({ queryKey: ["reading-history"], queryFn: () => api<Page<AttemptSummary>>("/reading/history?page_size=20") });
  const start = useMutation({
    mutationFn: (v: SetupValues) =>
      api<ReadingAttempt>("/reading/generate", {
        json: { difficulty: v.difficulty, topic: v.topic || null, question_count: v.question_count, time_limit_minutes: v.time_limit_minutes, question_types: v.question_types.length ? v.question_types : null },
      }),
    onSuccess: (attempt) => router.push(`/reading/${attempt.id}`),
    onError: (err) => push({ tone: "error", title: "Couldn't create a reading set", description: errorMessage(err) }),
  });
  const types = params.get("types")?.split(",").filter((t) => READING_TYPES.includes(t)) ?? [];
  const difficulty = Number(params.get("difficulty")) || null;
  return (
    <div className="space-y-6">
      <PageHeader title="Reading" description="Original passages at your level with IELTS-style question types. Every answer comes with the evidence from the text." />
      <AttemptSetup types={READING_TYPES} defaults={{ difficulty, types }} onStart={(v) => start.mutate(v)} starting={start.isPending} defaultCount={8} defaultMinutes={20} />
      <Card>
        <CardHeader title="Recent reading" />
        <CardBody>
          {history.isLoading ? (
            <Skeleton className="h-32" />
          ) : history.error ? (
            <ErrorState error={history.error} onRetry={() => history.refetch()} />
          ) : history.data?.items.length ? (
            <AttemptHistory items={history.data.items} base="/reading" />
          ) : (
            <EmptyState title="No reading practice yet" description="Your results and estimated reading band will appear here." />
          )}
        </CardBody>
      </Card>
    </div>
  );
}

export default function ReadingPage() {
  return (
    <Suspense>
      <ReadingHub />
    </Suspense>
  );
}
