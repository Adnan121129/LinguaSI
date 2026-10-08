"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { TopicPicker } from "@/components/practice/topic-picker";
import { ErrorState, Notice, PageHeader } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { PracticeSet } from "@/lib/types";

function NewPractice() {
  const params = useSearchParams();
  const router = useRouter();
  const focus = params.get("focus");
  const [error, setError] = useState<unknown>(null);
  const started = useRef(false);

  // Recommendations link here with ?focus=...; build that set straight away.
  useEffect(() => {
    if (!focus || started.current) return;
    started.current = true;
    api<PracticeSet>("/practice/sets", { json: { focus, item_count: 8 } })
      .then((practice) => router.replace(`/practice/${practice.id}`))
      .catch((err) => {
        if (err instanceof ApiError && err.code === "use_skill_practice") router.replace((err.details as { route: string }).route);
        else setError(err);
      });
  }, [focus, router]);

  if (focus) return error ? <ErrorState error={error} /> : <Notice tone="primary">Building your practice set…</Notice>;
  return (
    <div>
      <PageHeader title="Focused practice" description="Pick a grammar or language area. Each set mixes sentences from your own work with targeted exercises." />
      <TopicPicker />
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
