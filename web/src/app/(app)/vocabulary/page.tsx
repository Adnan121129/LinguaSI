"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { AreaTrendChart, ChartCard, SERIES_COLORS, shortDay } from "@/components/charts";
import { useToast } from "@/components/providers/toast";
import { Badge, Button, Card, CardBody, CardHeader, EmptyState, ErrorState, Input, PageHeader, PageSkeleton, Select, Skeleton, Stat, Tabs } from "@/components/ui";
import { ReviewSession } from "@/components/vocabulary/review-session";
import { api, errorMessage } from "@/lib/api";
import type { Page, UserWord, VocabInsights, VocabItem, VocabToday } from "@/lib/types";
import { formatDate, titleCase } from "@/lib/utils";

const STATE_TONE: Record<string, "default" | "primary" | "accent" | "success" | "warning"> = {
  new: "accent",
  learning: "warning",
  familiar: "primary",
  strong: "success",
  mastered: "success",
};
const GROUP_LABELS: Record<string, string> = {
  repeatedly_misunderstood: "Repeatedly misunderstood",
  forgotten: "Forgotten after learning",
  challenging: "Challenging",
  too_easy: "Too easy",
  in_progress: "In progress",
};

function TodayTab({ focus }: { focus: string | null }) {
  const [round, setRound] = useState(0);
  const today = useQuery({
    queryKey: ["vocab-today", focus, round],
    queryFn: () => api<VocabToday>(`/vocabulary/today${focus ? `?focus=${focus}` : ""}`),
    staleTime: Infinity,
  });
  if (today.isLoading) return <Skeleton className="h-72" />;
  if (today.error || !today.data) return <ErrorState error={today.error} onRetry={() => today.refetch()} />;
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2">
        <ReviewSession key={`${today.data.started_at}`} session={today.data} onFinished={() => setRound((r) => r + 1)} />
      </div>
      <Card className="h-fit">
        <CardHeader title="Today" description={focus === "collocation" ? "Focus: collocations for your writing" : "Due words first, then a few new ones"} />
        <CardBody className="grid grid-cols-2 gap-4">
          <Stat label="Due" value={today.data.due_count} />
          <Stat label="New" value={today.data.new_count} />
          <Stat label="Known" value={today.data.counts.known} />
          <Stat label="Recall" value={today.data.retention.accuracy === null ? "—" : `${Math.round(today.data.retention.accuracy)}%`} hint={`last ${today.data.retention.reviews} reviews`} />
        </CardBody>
      </Card>
    </div>
  );
}

function WordsTab() {
  const [state, setState] = useState("");
  const words = useQuery({ queryKey: ["vocab-words", state], queryFn: () => api<Page<UserWord>>(`/vocabulary/words?page_size=100${state ? `&state=${state}` : ""}`) });
  return (
    <Card>
      <div className="flex items-center gap-3 border-b border-border p-4">
        <Select aria-label="Filter by state" value={state} onChange={(e) => setState(e.target.value)} className="w-auto">
          <option value="">All words</option>
          {["new", "learning", "familiar", "strong", "mastered"].map((s) => (
            <option key={s} value={s}>
              {titleCase(s)}
            </option>
          ))}
        </Select>
        <span className="text-sm text-muted-foreground">{words.data?.total ?? 0} words</span>
      </div>
      {words.isLoading ? (
        <div className="p-5">
          <Skeleton className="h-40" />
        </div>
      ) : words.error ? (
        <div className="p-5">
          <ErrorState error={words.error} onRetry={() => words.refetch()} />
        </div>
      ) : words.data?.items.length ? (
        <ul className="divide-y divide-border">
          {words.data.items.map((w) => (
            <li key={w.user_vocab_id} className="flex flex-wrap items-start gap-3 px-5 py-3">
              <div className="min-w-0 flex-1">
                <p className="font-medium">
                  {w.item.word} <span className="text-sm font-normal text-muted-foreground">{w.item.part_of_speech} · {w.item.cefr}</span>
                </p>
                <p className="text-sm text-muted-foreground">{w.item.definition}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {w.correct_count} right · {w.incorrect_count} wrong · next {formatDate(w.due_at)}
                  {w.used_in_writing + w.used_in_speaking > 0 && ` · used ${w.used_in_writing}× in writing, ${w.used_in_speaking}× in speaking`}
                </p>
              </div>
              <Badge tone={STATE_TONE[w.state]}>{titleCase(w.state)}</Badge>
            </li>
          ))}
        </ul>
      ) : (
        <div className="p-5">
          <EmptyState title="No words here yet" description="Start today's review to add your first words." />
        </div>
      )}
    </Card>
  );
}

function BankTab() {
  const queryClient = useQueryClient();
  const { push } = useToast();
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [topic, setTopic] = useState("");
  const bank = useQuery({
    queryKey: ["vocab-bank", search, topic],
    queryFn: () => api<Page<VocabItem & { owned: boolean }>>(`/vocabulary/bank?page_size=30${search ? `&q=${encodeURIComponent(search)}` : ""}${topic ? `&topic=${topic}` : ""}`),
  });
  const add = useMutation({
    mutationFn: (itemId: number) => api("/vocabulary/words", { json: { item_id: itemId } }),
    onSuccess: () => {
      push({ tone: "success", title: "Added to your words", description: "It will appear in your next review." });
      queryClient.invalidateQueries({ queryKey: ["vocab-bank"] });
      queryClient.invalidateQueries({ queryKey: ["vocab-words"] });
    },
    onError: (err) => push({ tone: "error", title: "Couldn't add the word", description: errorMessage(err) }),
  });
  return (
    <div className="space-y-4">
      <form
        className="flex flex-wrap gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          setSearch(q.trim());
        }}
      >
        <div className="relative min-w-60 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search words and phrases" className="pl-9" aria-label="Search the word bank" />
        </div>
        <Select aria-label="Topic" value={topic} onChange={(e) => setTopic(e.target.value)} className="w-auto">
          <option value="">All topics</option>
          {["academic", "argument", "collocation", "daily_life", "economy", "education", "environment", "health", "society", "technology", "work", "travel"].map((t) => (
            <option key={t} value={t}>
              {titleCase(t)}
            </option>
          ))}
        </Select>
        <Button type="submit" variant="secondary">
          Search
        </Button>
      </form>
      {bank.isLoading ? (
        <Skeleton className="h-60" />
      ) : bank.error ? (
        <ErrorState error={bank.error} onRetry={() => bank.refetch()} />
      ) : bank.data?.items.length ? (
        <div className="grid gap-3 md:grid-cols-2">
          {bank.data.items.map((item) => (
            <Card key={item.id}>
              <CardBody className="space-y-1.5">
                <div className="flex items-start justify-between gap-2">
                  <p className="font-semibold">
                    {item.word} <span className="text-sm font-normal text-muted-foreground">{item.part_of_speech} · {item.cefr}</span>
                  </p>
                  {item.owned ? (
                    <Badge tone="success">In your words</Badge>
                  ) : (
                    <Button size="sm" variant="secondary" onClick={() => add.mutate(item.id)} disabled={add.isPending} aria-label={`Add ${item.word}`}>
                      <Plus className="size-3.5" /> Add
                    </Button>
                  )}
                </div>
                <p className="text-sm">{item.definition}</p>
                <p className="text-sm italic text-muted-foreground">{item.example}</p>
              </CardBody>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState title="No words found" description="Try another search or topic." />
      )}
    </div>
  );
}

function InsightsTab() {
  const insights = useQuery({ queryKey: ["vocab-insights"], queryFn: () => api<VocabInsights>("/vocabulary/insights") });
  if (insights.isLoading) return <Skeleton className="h-72" />;
  if (insights.error || !insights.data) return <ErrorState error={insights.error} onRetry={() => insights.refetch()} />;
  const d = insights.data;
  return (
    <div className="space-y-6">
      <Card>
        <CardBody className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          {(["new", "learning", "familiar", "strong", "mastered"] as const).map((s) => (
            <Stat key={s} label={titleCase(s)} value={d.counts[s]} />
          ))}
          <Stat label="Recall accuracy" value={d.retention.accuracy === null ? "—" : `${Math.round(d.retention.accuracy)}%`} hint={`last ${d.retention.reviews} reviews`} />
        </CardBody>
      </Card>
      <ChartCard
        question="Is my vocabulary growing?"
        description="Words you know (familiar or better) and words mastered"
        rows={d.growth}
        columns={[
          { key: "day", label: "Day" },
          { key: "known", label: "Known" },
          { key: "mastered", label: "Mastered" },
        ]}
        legend={[
          { label: "Known", color: SERIES_COLORS.known },
          { label: "Mastered", color: SERIES_COLORS.mastered },
        ]}
      >
        <AreaTrendChart
          data={d.growth}
          xKey="day"
          xFormat={shortDay}
          series={[
            { key: "known", label: "Known", color: SERIES_COLORS.known },
            { key: "mastered", label: "Mastered", color: SERIES_COLORS.mastered },
          ]}
        />
      </ChartCard>
      <div className="grid gap-4 md:grid-cols-2">
        {Object.entries(GROUP_LABELS).map(([key, label]) =>
          d.groups[key]?.length ? (
            <Card key={key}>
              <CardHeader title={label} description={`${d.group_counts[key] ?? d.groups[key].length} words`} />
              <CardBody className="flex flex-wrap gap-1.5">
                {d.groups[key].map((w) => (
                  <Badge key={w}>{w}</Badge>
                ))}
              </CardBody>
            </Card>
          ) : null,
        )}
        {(d.used_in_writing.length > 0 || d.used_in_speaking.length > 0) && (
          <Card>
            <CardHeader title="Words you've used in context" description="Using a word in writing or speaking counts as a successful review." />
            <CardBody className="space-y-2 text-sm">
              {d.used_in_writing.length > 0 && <p>Writing: {d.used_in_writing.join(", ")}</p>}
              {d.used_in_speaking.length > 0 && <p>Speaking: {d.used_in_speaking.join(", ")}</p>}
            </CardBody>
          </Card>
        )}
      </div>
    </div>
  );
}

function VocabularyHub() {
  const params = useSearchParams();
  const focus = params.get("focus");
  const [tab, setTab] = useState<"today" | "words" | "bank" | "insights">("today");
  return (
    <div>
      <PageHeader title="Vocabulary" description="Adaptive spaced repetition: words come back just before you're likely to forget them, and SI adds words from your own writing and speaking." />
      <div className="mb-5">
        <Tabs
          value={tab}
          onChange={setTab}
          items={[
            { value: "today", label: "Today's review" },
            { value: "words", label: "My words" },
            { value: "bank", label: "Word bank" },
            { value: "insights", label: "Insights" },
          ]}
        />
      </div>
      {tab === "today" && <TodayTab focus={focus} />}
      {tab === "words" && <WordsTab />}
      {tab === "bank" && <BankTab />}
      {tab === "insights" && <InsightsTab />}
    </div>
  );
}

export default function VocabularyPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <VocabularyHub />
    </Suspense>
  );
}
