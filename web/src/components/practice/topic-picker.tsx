"use client";

import { useQuery } from "@tanstack/react-query";
import { BookMarked, Puzzle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, Card, CardBody, ErrorState, Skeleton } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { PracticeSet } from "@/lib/types";

type Topic = { focus: string; label: string; items: number; guide: string | null };

/** Grammar and language-area picker that builds a practice set and opens it. */
export function TopicPicker() {
  const router = useRouter();
  const [creating, setCreating] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const topics = useQuery({ queryKey: ["practice-topics"], queryFn: () => api<Topic[]>("/practice/topics") });

  async function create(focus: string) {
    setCreating(focus);
    setError(null);
    try {
      const practice = await api<PracticeSet>("/practice/sets", { json: { focus, item_count: 8 } });
      router.push(`/practice/${practice.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.code === "use_skill_practice") return router.push((err.details as { route: string }).route);
      setError(err);
      setCreating(null);
    }
  }

  if (topics.isLoading) return <Skeleton className="h-64" />;
  if (topics.error) return <ErrorState error={topics.error} onRetry={() => topics.refetch()} />;
  return (
    <div className="space-y-4">
      {error ? <ErrorState error={error} /> : null}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {topics.data?.map((t) => (
          <Card key={t.focus}>
            <CardBody className="flex h-full flex-col gap-2">
              <p className="flex items-center gap-2 font-semibold">
                <Puzzle className="size-4 text-primary" aria-hidden /> {t.label}
              </p>
              {t.guide && <p className="line-clamp-3 text-sm text-muted-foreground">{t.guide}</p>}
              <p className="mt-auto flex items-center gap-1 text-xs text-muted-foreground">
                <BookMarked className="size-3.5" aria-hidden /> {t.items} exercises in the bank
              </p>
              <Button size="sm" variant="secondary" onClick={() => create(t.focus)} loading={creating === t.focus} disabled={!!creating}>
                Practise
              </Button>
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  );
}
