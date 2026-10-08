"use client";

import { useQuery } from "@tanstack/react-query";
import { BookMarked, Puzzle } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { Button, Card, CardBody, ErrorState, Notice, PageHeader, Skeleton } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { PracticeSet } from "@/lib/types";

type Topic = { focus: string; label: string; items: number; guide: string | null };

function NewPractice() {
  const params = useSearchParams();
  const router = useRouter();
  const focus = params.get("focus");
  const [error, setError] = useState<unknown>(null);
  const [creating, setCreating] = useState<string | null>(null);
  const started = useRef(false);
  const topics = useQuery({ queryKey: ["practice-topics"], queryFn: () => api<Topic[]>("/practice/topics"), enabled: !focus });

  const create = async (topic: string) => {
    setCreating(topic);
    setError(null);
    try {
      const practice = await api<PracticeSet>("/practice/sets", { json: { focus: topic, item_count: 8 } });
      router.replace(`/practice/${practice.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.code === "use_skill_practice") {
        router.replace((err.details as { route: string }).route);
        return;
      }
      setError(err);
      setCreating(null);
    }
  };

  // Recommendations link here with ?focus=...; build that set straight away.
  useEffect(() => {
    if (focus && !started.current) {
      started.current = true;
      void create(focus);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus]);

  if (focus) {
    return error ? <ErrorState error={error} onRetry={() => create(focus)} /> : <Notice tone="primary">Building your practice set…</Notice>;
  }
  return (
    <div>
      <PageHeader title="Focused practice" description="Pick a grammar or language area. Each set mixes sentences from your own work with targeted exercises." />
      {error ? <ErrorState error={error} /> : null}
      {topics.isLoading ? (
        <Skeleton className="h-64" />
      ) : topics.error ? (
        <ErrorState error={topics.error} onRetry={() => topics.refetch()} />
      ) : (
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
                <Button size="sm" variant="secondary" onClick={() => create(t.focus)} loading={creating === t.focus}>
                  Practise
                </Button>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

export default function NewPracticePage() {
  return (
    <Suspense>
      <NewPractice />
    </Suspense>
  );
}
