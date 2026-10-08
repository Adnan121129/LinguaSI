"use client";

import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { PracticeRunner } from "@/components/practice/practice-runner";
import { Button, ErrorState, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import type { PracticeSet } from "@/lib/types";

export default function SentenceBuildingPage() {
  const create = useMutation({ mutationFn: () => api<PracticeSet>("/lab/sentence-building", { method: "POST" }) });
  const started = useRef(false);
  useEffect(() => {
    if (!started.current) {
      started.current = true;
      create.mutate();
    }
  }, [create]);
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Sentence building"
        description="Rebuild natural sentences from scrambled words — great for word order and collocations."
        action={
          create.data?.status === "completed" || create.isSuccess ? (
            <Button variant="outline" onClick={() => create.mutate()} loading={create.isPending}>
              New set
            </Button>
          ) : null
        }
      />
      {create.isPending ? <Skeleton className="h-72" /> : create.error ? <ErrorState error={create.error} onRetry={() => create.mutate()} /> : create.data ? <PracticeRunner key={create.data.id} practice={create.data} exit={{ href: "/lab", label: "Back to the Lab" }} /> : null}
    </div>
  );
}
