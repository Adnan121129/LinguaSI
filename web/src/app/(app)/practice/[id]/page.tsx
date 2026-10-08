"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import { PracticeRunner } from "@/components/practice/practice-runner";
import { ErrorState, PageHeader, PageSkeleton } from "@/components/ui";
import { api } from "@/lib/api";
import type { PracticeSet } from "@/lib/types";

export default function PracticePage() {
  const { id } = useParams<{ id: string }>();
  const practiceId = Number(id);
  const { data, error, isLoading, refetch } = useQuery({ queryKey: ["practice", practiceId], queryFn: () => api<PracticeSet>(`/practice/sets/${practiceId}`) });
  if (isLoading) return <PageSkeleton />;
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />;
  return (
    <div className="mx-auto max-w-3xl">
      <Link href="/mistakes" className="text-sm text-muted-foreground hover:text-foreground">
        ← My Mistakes
      </Link>
      <PageHeader title={data.title} description={`${data.description} · about ${data.estimated_minutes} min`} />
      <PracticeRunner key={data.id} practice={data} />
    </div>
  );
}
