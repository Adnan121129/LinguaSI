"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, CheckCircle2, ChevronDown, Dumbbell, RotateCcw, Sparkles, Target } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { ChartCard, ColumnChart, MatrixHeatmap, shortWeek } from "@/components/charts";
import { useToast } from "@/components/providers/toast";
import { Badge, Button, Card, CardBody, CardHeader, EmptyState, ErrorState, PageHeader, PageSkeleton, Select, Skeleton, Stat } from "@/components/ui";
import { ApiError, api, errorMessage } from "@/lib/api";
import type { Mistake, MistakeDetail, MistakeSummary, Page, PracticeSet } from "@/lib/types";
import { cn, relativeTime, titleCase } from "@/lib/utils";

const STATUS_TONE = { unresolved: "warning", corrected: "primary", mastered: "success" } as const;

function MistakeRow({ mistake, open, onToggle }: { mistake: Mistake; open: boolean; onToggle: () => void }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { push } = useToast();
  const detail = useQuery({ queryKey: ["mistake", mistake.id], queryFn: () => api<MistakeDetail>(`/mistakes/${mistake.id}`), enabled: open });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["mistakes"] });
    queryClient.invalidateQueries({ queryKey: ["mistake-summary"] });
    queryClient.invalidateQueries({ queryKey: ["mistake", mistake.id] });
  };
  const status = useMutation({
    mutationFn: (body: { status?: string; revisit_in_days?: number }) => api<Mistake>(`/mistakes/${mistake.id}/status`, { json: body }),
    onSuccess: (_, body) => {
      push({ tone: "success", title: body.revisit_in_days ? `We'll bring this back in ${body.revisit_in_days} days` : body.status === "mastered" ? "Marked as mastered" : "Reopened" });
      refresh();
    },
    onError: (err) => push({ tone: "error", title: "Couldn't update this mistake", description: errorMessage(err) }),
  });
  const practise = useMutation({
    mutationFn: () => api<PracticeSet>(`/mistakes/${mistake.id}/practice`, { method: "POST" }),
    onSuccess: (ps) => router.push(`/practice/${ps.id}`),
    onError: (err) => {
      if (err instanceof ApiError && err.code === "use_skill_practice") router.push((err.details as { route: string }).route);
      else push({ tone: "error", title: "Couldn't build practice", description: errorMessage(err) });
    },
  });
  const skillPractice = mistake.category === "comprehension" || mistake.category === "fluency";

  return (
    <li className="border-b border-border last:border-0">
      <button onClick={onToggle} aria-expanded={open} className="flex w-full items-start gap-3 px-5 py-4 text-left hover:bg-muted/40">
        <div className="min-w-0 flex-1 space-y-1">
          <p className="text-sm">
            <span className="mark-error">{mistake.original}</span>
            {!skillPractice && (
              <>
                {" "}
                → <span className="font-medium text-success">{mistake.corrected}</span>
              </>
            )}
          </p>
          <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            <Badge>{mistake.label}</Badge>
            <span>{titleCase(mistake.source)}</span>·<span>{relativeTime(mistake.last_seen_at)}</span>
            {mistake.occurrences > 1 && <Badge tone="danger">×{mistake.occurrences}</Badge>}
          </div>
        </div>
        <Badge tone={STATUS_TONE[mistake.status]}>{titleCase(mistake.status)}</Badge>
        <ChevronDown className={cn("mt-0.5 size-4 shrink-0 text-muted-foreground transition", open && "rotate-180")} aria-hidden />
      </button>
      {open && (
        <div className="space-y-4 px-5 pb-5">
          <p className="text-sm">{mistake.explanation}</p>
          {mistake.context && <p className="rounded-xl bg-muted p-3 text-sm text-muted-foreground">“{mistake.context}”</p>}
          {detail.isLoading ? (
            <Skeleton className="h-16" />
          ) : detail.data?.guide ? (
            <div className="rounded-xl border border-border p-3 text-sm">
              <p className="font-medium">{detail.data.guide.title ?? mistake.label}</p>
              {detail.data.guide.rule && <p className="mt-1">{detail.data.guide.rule}</p>}
              {detail.data.guide.tip && <p className="mt-1 text-muted-foreground">Tip: {detail.data.guide.tip}</p>}
            </div>
          ) : null}
          <p className="text-xs text-muted-foreground">
            Practised {mistake.practice_attempts} time{mistake.practice_attempts === 1 ? "" : "s"} · {mistake.practice_correct} correct · two correct practices in a row mark it as mastered.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => practise.mutate()} loading={practise.isPending}>
              <Dumbbell className="size-3.5" /> {skillPractice ? "Practise this question type" : "Mini practice"}
            </Button>
            {mistake.status !== "mastered" ? (
              <Button size="sm" variant="outline" onClick={() => status.mutate({ status: "mastered" })} disabled={status.isPending}>
                <CheckCircle2 className="size-3.5" /> Mark mastered
              </Button>
            ) : (
              <Button size="sm" variant="outline" onClick={() => status.mutate({ status: "unresolved" })} disabled={status.isPending}>
                <RotateCcw className="size-3.5" /> Reopen
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={() => status.mutate({ revisit_in_days: 3 })} disabled={status.isPending}>
              <CalendarClock className="size-3.5" /> Revisit in 3 days
            </Button>
          </div>
        </div>
      )}
    </li>
  );
}

function MistakesTracker() {
  const params = useSearchParams();
  const router = useRouter();
  const { push } = useToast();
  const [status, setStatus] = useState(params.get("status") ?? "");
  const [category, setCategory] = useState("");
  const [source, setSource] = useState("");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<number | null>(Number(params.get("focus")) || null);

  const summary = useQuery({ queryKey: ["mistake-summary"], queryFn: () => api<MistakeSummary>("/mistakes/summary") });
  const query = new URLSearchParams({ page: String(page), page_size: "15" });
  if (status) query.set("status", status);
  if (category) query.set("category", category);
  if (source) query.set("source", source);
  const list = useQuery({ queryKey: ["mistakes", status, category, source, page], queryFn: () => api<Page<Mistake>>(`/mistakes?${query}`) });

  const revision = useMutation({
    mutationFn: () => api<PracticeSet>("/mistakes/revision", { method: "POST" }),
    onSuccess: (ps) => router.push(`/practice/${ps.id}`),
    onError: (err) => push({ tone: "warning", title: "No revision session yet", description: errorMessage(err) }),
  });

  if (summary.isLoading) return <PageSkeleton />;
  if (summary.error || !summary.data) return <ErrorState error={summary.error} onRetry={() => summary.refetch()} />;
  const s = summary.data;

  return (
    <div className="space-y-6">
      <PageHeader
        title="My Mistakes"
        description="Every mistake from writing, speaking, vocabulary, reading and listening — grouped, tracked and practised until you master it."
        action={
          <Button onClick={() => revision.mutate()} loading={revision.isPending}>
            <Sparkles className="size-4" /> 5-minute revision{s.due_for_revision ? ` (${s.due_for_revision} due)` : ""}
          </Button>
        }
      />

      <Card>
        <CardBody className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Stat label="Tracked" value={s.totals.total} hint={`${s.totals.occurrences} occurrences`} icon={<Target className="size-4" />} />
          <Stat label="To fix" value={s.totals.unresolved} />
          <Stat label="Corrected" value={s.totals.corrected} />
          <Stat label="Mastered" value={s.totals.mastered} />
        </CardBody>
      </Card>

      {s.totals.total === 0 ? (
        <EmptyState title="No mistakes tracked yet" description="Complete a writing task, a speaking test or some practice and SI will start tracking your patterns here." />
      ) : (
        <>
          <div className="grid gap-6 lg:grid-cols-2">
            <ChartCard
              question="Which kinds of mistakes do I make most?"
              description="All tracked mistakes by category"
              rows={s.by_category}
              columns={[
                { key: "label", label: "Category" },
                { key: "count", label: "Mistakes" },
              ]}
            >
              <ColumnChart data={s.by_category} xKey="label" yKey="count" label="Mistakes" height={220} />
            </ChartCard>
            <ChartCard
              question="Am I making fewer mistakes?"
              description="New mistakes recorded per week"
              rows={s.weekly_trend}
              columns={[
                { key: "week", label: "Week" },
                { key: "count", label: "New mistakes" },
              ]}
            >
              <ColumnChart data={s.weekly_trend} xKey="week" yKey="count" label="New mistakes" xFormat={shortWeek} height={220} />
            </ChartCard>
          </div>
          <ChartCard
            question="When and where do my mistakes happen?"
            description="Mistakes per category each week — darker means more"
            rows={s.heatmap.rows.map((r) => ({ label: r.label, ...Object.fromEntries(s.heatmap.weeks.map((w, i) => [w, r.values[i]])) }))}
            columns={[{ key: "label", label: "Category" }, ...s.heatmap.weeks.map((w) => ({ key: w, label: shortWeek(w) }))]}
          >
            <MatrixHeatmap columns={s.heatmap.weeks} rows={s.heatmap.rows} />
          </ChartCard>
          {s.recurring.length > 0 && (
            <Card>
              <CardHeader title="Recurring patterns" description="Mistakes you keep making in the last 60 days" />
              <CardBody>
                <ul className="grid gap-3 md:grid-cols-2">
                  {s.recurring.map((r) => (
                    <li key={r.subcategory} className="rounded-xl border border-border p-3 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{r.label}</span>
                        <Badge tone="danger">{r.count}×</Badge>
                      </div>
                      {r.example && (
                        <p className="mt-1 text-muted-foreground">
                          e.g. “{r.example.original}” → “{r.example.corrected}”
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              </CardBody>
            </Card>
          )}
        </>
      )}

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-border p-4">
          <Select aria-label="Status" value={status} onChange={(e) => (setStatus(e.target.value), setPage(1))} className="w-auto">
            <option value="">All statuses</option>
            <option value="unresolved">To fix</option>
            <option value="recurring">Recurring</option>
            <option value="due">Due for revision</option>
            <option value="corrected">Corrected</option>
            <option value="mastered">Mastered</option>
          </Select>
          <Select aria-label="Category" value={category} onChange={(e) => (setCategory(e.target.value), setPage(1))} className="w-auto">
            <option value="">All categories</option>
            {s.by_category.map((c) => (
              <option key={c.category} value={c.category}>
                {c.label}
              </option>
            ))}
          </Select>
          <Select aria-label="Source" value={source} onChange={(e) => (setSource(e.target.value), setPage(1))} className="w-auto">
            <option value="">All skills</option>
            {["writing", "speaking", "vocabulary", "reading", "listening", "practice"].map((src) => (
              <option key={src} value={src}>
                {titleCase(src)}
              </option>
            ))}
          </Select>
        </div>
        {list.isLoading ? (
          <div className="p-5">
            <Skeleton className="h-40" />
          </div>
        ) : list.error ? (
          <div className="p-5">
            <ErrorState error={list.error} onRetry={() => list.refetch()} />
          </div>
        ) : list.data?.items.length ? (
          <>
            <ul>
              {list.data.items.map((m) => (
                <MistakeRow key={m.id} mistake={m} open={openId === m.id} onToggle={() => setOpenId(openId === m.id ? null : m.id)} />
              ))}
            </ul>
            {list.data.total > list.data.page_size && (
              <div className="flex items-center justify-between border-t border-border p-4 text-sm">
                <span className="text-muted-foreground">
                  Page {page} of {Math.ceil(list.data.total / list.data.page_size)}
                </span>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
                    Previous
                  </Button>
                  <Button size="sm" variant="outline" disabled={page * list.data.page_size >= list.data.total} onClick={() => setPage((p) => p + 1)}>
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="p-5">
            <EmptyState title="Nothing matches these filters" />
          </div>
        )}
      </Card>
    </div>
  );
}

export default function MistakesPage() {
  return (
    <Suspense>
      <MistakesTracker />
    </Suspense>
  );
}
