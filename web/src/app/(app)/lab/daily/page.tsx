"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Volume2 } from "lucide-react";

import { PracticeRunner } from "@/components/practice/practice-runner";
import { Button, Card, CardBody, ErrorState, PageHeader, PageSkeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { speak, ttsSupported } from "@/lib/speech";
import type { LabOverview, PracticeSet } from "@/lib/types";

export default function DailyEnglishPage() {
  const phrase = useQuery({ queryKey: ["lab-daily"], queryFn: () => api<LabOverview["daily_phrase"]>("/lab/daily") });
  const quiz = useMutation({ mutationFn: () => api<PracticeSet>("/lab/daily/quiz", { method: "POST" }) });
  if (phrase.isLoading) return <PageSkeleton />;
  if (phrase.error || !phrase.data) return <ErrorState error={phrase.error} onRetry={() => phrase.refetch()} />;
  const p = phrase.data;
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title="Daily English" description="One useful everyday expression a day, plus a quick quiz that recycles earlier phrases." />
      <Card>
        <CardBody className="space-y-2">
          <div className="flex items-center justify-between gap-3">
            <p className="text-3xl font-semibold">{p.phrase}</p>
            {ttsSupported() && (
              <Button variant="ghost" onClick={() => speak(`${p.phrase}. ${p.example}`, { rate: 0.95 })} aria-label="Listen to the phrase">
                <Volume2 className="size-5" />
              </Button>
            )}
          </div>
          <p className="text-lg">{p.meaning}</p>
          <p className="italic text-muted-foreground">“{p.example}”</p>
        </CardBody>
      </Card>
      {quiz.data ? (
        <PracticeRunner key={quiz.data.id} practice={quiz.data} exit={{ href: "/lab", label: "Back to the Lab" }} />
      ) : (
        <>
          {quiz.error ? <ErrorState error={quiz.error} /> : null}
          <Button size="lg" onClick={() => quiz.mutate()} loading={quiz.isPending}>
            Take the 1-minute quiz
          </Button>
        </>
      )}
    </div>
  );
}
