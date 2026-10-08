"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpen, CalendarDays, FlaskConical, Headphones, Library, MessagesSquare, Mic, PenLine, Puzzle, Shuffle } from "lucide-react";
import Link from "next/link";

import { Card, CardBody, ErrorState, PageHeader, PageSkeleton } from "@/components/ui";
import { api } from "@/lib/api";
import type { LabOverview } from "@/lib/types";

const ICONS: Record<string, typeof FlaskConical> = {
  grammar: Puzzle,
  vocabulary: Library,
  pronunciation: Mic,
  conversation: MessagesSquare,
  sentence_building: Shuffle,
  reading: BookOpen,
  listening: Headphones,
  writing: PenLine,
  daily: CalendarDays,
};

export default function LabPage() {
  const { data, error, isLoading, refetch } = useQuery({ queryKey: ["lab"], queryFn: () => api<LabOverview>("/lab") });
  if (isLoading) return <PageSkeleton />;
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />;
  return (
    <div className="space-y-6">
      <PageHeader title="English Lab" description="Everyday English beyond the exam: grammar, pronunciation, conversation, sentence building and a phrase a day." />
      <Card className="bg-gradient-to-br from-primary-soft to-accent-soft">
        <CardBody>
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">Phrase of the day</p>
          <p className="mt-1 text-2xl font-semibold">{data.daily_phrase.phrase}</p>
          <p className="mt-1">{data.daily_phrase.meaning}</p>
          <p className="mt-2 text-sm italic text-muted-foreground">“{data.daily_phrase.example}”</p>
          <Link href="/lab/daily" className="mt-3 inline-block text-sm font-medium text-primary">
            Practise today&apos;s phrase →
          </Link>
        </CardBody>
      </Card>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data.sections.map((section) => {
          const Icon = ICONS[section.key] ?? FlaskConical;
          return (
            <Link key={section.key} href={section.route} className="group">
              <Card className="h-full transition group-hover:border-primary/40">
                <CardBody className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="rounded-xl bg-primary-soft p-2 text-primary">
                      <Icon className="size-5" aria-hidden />
                    </div>
                    {section.count !== null && <span className="text-xs text-muted-foreground">{section.count} available</span>}
                  </div>
                  <p className="font-semibold">{section.title}</p>
                  <p className="text-sm text-muted-foreground">{section.description}</p>
                </CardBody>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
