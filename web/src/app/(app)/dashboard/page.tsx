"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Brain, CalendarDays, Flame, GraduationCap, Library, Sparkles, Target, TrendingDown, TrendingUp, Zap } from "lucide-react";
import Link from "next/link";

import { BandValue, OFFICIAL_DISCLAIMER } from "@/components/band";
import { ColumnChart } from "@/components/charts";
import { MissionCard, RecommendationCard, SIFeed } from "@/components/learning-cards";
import { Card, CardBody, CardHeader, EmptyState, ErrorState, Notice, PageSkeleton, ProgressBar, buttonClasses } from "@/components/ui";
import { api } from "@/lib/api";
import type { Dashboard } from "@/lib/types";
import { cn, formatBand } from "@/lib/utils";

function TrendIcon({ trend }: { trend: string }) {
  if (trend === "improving") return <TrendingUp className="size-4 text-success" aria-label="Improving" />;
  if (trend === "declining") return <TrendingDown className="size-4 text-danger" aria-label="Declining" />;
  return null;
}

export default function DashboardPage() {
  const { data, error, isLoading, refetch } = useQuery({ queryKey: ["dashboard"], queryFn: () => api<Dashboard>("/dashboard") });
  if (isLoading) return <PageSkeleton />;
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />;

  const ielts = data.goal === "ielts";
  const weeklyGoal = data.weekly_goal_minutes || 1;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{data.greeting}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {data.goal_label}
            {data.days_to_test !== null && data.days_to_test >= 0 && <> · {data.days_to_test} days to your test</>}
          </p>
        </div>
      </div>

      {!data.diagnostic_completed && (
        <Notice tone="primary" icon={<GraduationCap className="mt-0.5 size-4 text-primary" />}>
          <span className="font-medium">Take the 15-minute diagnostic</span> so SI can estimate your level and plan the right practice.{" "}
          <Link href="/onboarding/diagnostic" className="font-medium text-primary underline">
            Start now
          </Link>
        </Notice>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-5">
          {ielts ? (
            <>
              <BandValue band={data.estimated_band} size="lg" target={data.target_band} />
              <p className="mt-2 text-sm text-muted-foreground">
                Target {formatBand(data.target_band)} · {data.cefr ?? "—"} level
              </p>
              <ProgressBar className="mt-3" value={((data.estimated_band ?? 0) / data.target_band) * 100} tone="primary" label="Progress to target band" />
            </>
          ) : (
            <>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">AI Estimated Level</p>
              <p className="text-4xl font-semibold">{data.cefr ?? "—"}</p>
              <p className="mt-2 text-sm text-muted-foreground">CEFR estimate from your recent practice</p>
            </>
          )}
        </Card>
        <Card className="p-5">
          <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            <Flame className={cn("size-3.5", data.streak.current ? "text-danger" : "")} aria-hidden /> Streak
          </p>
          <p className="mt-1 text-4xl font-semibold">{data.streak.current} <span className="text-base font-normal text-muted-foreground">days</span></p>
          <p className="mt-2 text-sm text-muted-foreground">
            {data.streak.active_today ? "Done for today — nice." : data.streak.at_risk ? "Practise today to keep your streak." : "Start a streak today."}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Best {data.streak.longest} · {data.streak.freezes} streak freeze{data.streak.freezes === 1 ? "" : "s"}
          </p>
        </Card>
        <Card className="p-5">
          <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            <Zap className="size-3.5" aria-hidden /> Level {data.level.level}
          </p>
          <p className="mt-1 text-xl font-semibold">{data.level.title}</p>
          <ProgressBar className="mt-3" value={data.level.progress * 100} label="Progress to next level" />
          <p className="mt-2 text-xs text-muted-foreground">
            {data.level.xp.toLocaleString()} XP · {Math.max(0, data.level.next_level_xp - data.level.xp).toLocaleString()} to next level · +{data.today_xp} today
          </p>
        </Card>
        <Card className="p-5">
          <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            <CalendarDays className="size-3.5" aria-hidden /> This week
          </p>
          <p className="mt-1 text-4xl font-semibold">
            {data.weekly_minutes} <span className="text-base font-normal text-muted-foreground">/ {weeklyGoal} min</span>
          </p>
          <ProgressBar className="mt-3" value={(data.weekly_minutes / weeklyGoal) * 100} tone="success" label="Weekly study minutes" />
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {data.recommendation && <RecommendationCard rec={data.recommendation} primary />}
          {data.mission ? <MissionCard mission={data.mission} /> : <EmptyState title="No mission yet" description="Your daily mission appears once SI knows a little about you." />}
          {data.insight && (
            <Card>
              <CardHeader icon={<Brain className="size-4" />} title="Learning insight" description={data.insight.headline} />
              <CardBody className="space-y-2 text-sm">
                {data.insight.weakness && (
                  <p>
                    <span className="font-medium">{data.insight.weakness}</span> <span className="text-muted-foreground">{data.insight.weakness_reason}</span>
                  </p>
                )}
                {data.insight.suggestion && <p className="text-primary">{data.insight.suggestion}</p>}
              </CardBody>
            </Card>
          )}
          <Card>
            <CardHeader title="Skills overview" description="AI estimated scores from your recent practice (0–100), with the current difficulty level." action={<Link href="/progress" className="text-sm font-medium text-primary">Progress →</Link>} />
            <CardBody>
              <div className="grid gap-4 sm:grid-cols-2">
                {data.skills.map((s) => (
                  <div key={s.skill} className="space-y-1.5">
                    <div className="flex items-center justify-between text-sm">
                      <span className="flex items-center gap-1.5 font-medium">
                        {s.label} <TrendIcon trend={s.trend} />
                      </span>
                      <span className="text-muted-foreground">
                        {s.attempts ? (
                          <>
                            {s.band !== null ? `Band ${formatBand(s.band)} · ` : ""}
                            {Math.round(s.score ?? 0)}/100 · L{s.difficulty}
                          </>
                        ) : (
                          "Not practised yet"
                        )}
                      </span>
                    </div>
                    <ProgressBar value={s.score ?? 0} label={`${s.label} score`} />
                  </div>
                ))}
              </div>
            </CardBody>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Did I study enough this week?" description={`Minutes per day · the line marks your ${Math.round(weeklyGoal / 7)}-minute daily goal`} />
            <CardBody>
              <ColumnChart data={data.weekly} xKey="label" yKey="minutes" label="Minutes" unit=" min" reference={{ value: Math.round(weeklyGoal / 7), label: "" }} height={160} />
            </CardBody>
          </Card>
          <Card>
            <CardHeader icon={<Library className="size-4" />} title="Vocabulary" action={<Link href="/vocabulary" className="text-sm font-medium text-primary">Review →</Link>} />
            <CardBody className="space-y-3 text-sm">
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded-xl bg-muted p-2">
                  <p className="text-lg font-semibold">{data.vocabulary.known}</p>
                  <p className="text-xs text-muted-foreground">known</p>
                </div>
                <div className="rounded-xl bg-muted p-2">
                  <p className="text-lg font-semibold">{data.vocabulary.mastered}</p>
                  <p className="text-xs text-muted-foreground">mastered</p>
                </div>
                <div className="rounded-xl bg-muted p-2">
                  <p className="text-lg font-semibold">{data.vocabulary.due}</p>
                  <p className="text-xs text-muted-foreground">due now</p>
                </div>
              </div>
            </CardBody>
          </Card>
          {data.weaknesses.length > 0 && (
            <Card>
              <CardHeader icon={<Target className="size-4" />} title="Focus areas" />
              <CardBody className="space-y-3 text-sm">
                {data.weaknesses.map((w) => (
                  <div key={w.key}>
                    <p className="font-medium">{w.label}</p>
                    <p className="text-muted-foreground">{w.reason}</p>
                  </div>
                ))}
                <Link href="/mistakes" className={buttonClasses("outline", "sm", "w-full")}>
                  Open My Mistakes <ArrowRight className="size-3.5" />
                </Link>
              </CardBody>
            </Card>
          )}
          <Card>
            <CardHeader icon={<Sparkles className="size-4" />} title="What SI changed" description="Cross-skill actions from your recent activity" />
            <CardBody>
              <SIFeed events={data.si_feed.slice(0, 5)} />
            </CardBody>
          </Card>
          {data.recommendations.length > 1 && (
            <div className="space-y-3">
              <h2 className="text-sm font-semibold text-muted-foreground">More recommendations</h2>
              {data.recommendations
                .filter((r) => r.id !== data.recommendation?.id)
                .slice(0, 3)
                .map((r) => (
                  <RecommendationCard key={r.id} rec={r} />
                ))}
            </div>
          )}
        </div>
      </div>
      {ielts && <p className="text-xs text-muted-foreground">{OFFICIAL_DISCLAIMER}</p>}
    </div>
  );
}
