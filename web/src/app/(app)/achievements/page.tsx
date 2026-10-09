"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AudioLines,
  Award,
  Blocks,
  BookOpen,
  BookOpenCheck,
  Crown,
  Flag,
  Flame,
  Hammer,
  Headphones,
  Library,
  Lock,
  Medal,
  MessageCircleQuestion,
  Mic,
  Mountain,
  NotebookPen,
  Orbit,
  PenLine,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  Trophy,
} from "lucide-react";

import { MissionCard } from "@/components/learning-cards";
import { Badge, Card, CardBody, CardHeader, ErrorState, PageHeader, PageSkeleton, ProgressBar, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import type { AchievementsResponse, MissionsResponse } from "@/lib/types";
import { cn, formatDate, relativeTime } from "@/lib/utils";

// Icon names come from the achievements seed file.
const ICONS: Record<string, typeof Award> = {
  "audio-lines": AudioLines,
  blocks: Blocks,
  "book-open": BookOpen,
  "book-open-check": BookOpenCheck,
  crown: Crown,
  flag: Flag,
  flame: Flame,
  hammer: Hammer,
  headphones: Headphones,
  library: Library,
  medal: Medal,
  "message-circle-question": MessageCircleQuestion,
  mic: Mic,
  mountain: Mountain,
  "notebook-pen": NotebookPen,
  orbit: Orbit,
  "pen-line": PenLine,
  "shield-check": ShieldCheck,
  sparkles: Sparkles,
  target: Target,
  "trending-up": TrendingUp,
  trophy: Trophy,
};
const TIER_TONE: Record<string, "default" | "warning" | "primary" | "accent"> = { bronze: "warning", silver: "default", gold: "primary" };

export default function AchievementsPage() {
  const achievements = useQuery({ queryKey: ["achievements"], queryFn: () => api<AchievementsResponse>("/achievements") });
  const missions = useQuery({ queryKey: ["missions"], queryFn: () => api<MissionsResponse>("/missions") });
  if (achievements.isLoading || missions.isLoading) return <PageSkeleton />;
  if (achievements.error || !achievements.data) return <ErrorState error={achievements.error} onRetry={() => achievements.refetch()} />;
  const a = achievements.data;
  const earned = a.achievements.filter((x) => x.earned).length;
  return (
    <div className="space-y-6">
      <PageHeader title="Achievements" description="XP, levels, streaks, badges, daily missions and weekly challenges." />
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="p-5">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Level {a.level.level}</p>
          <p className="mt-1 text-2xl font-semibold">{a.level.title}</p>
          <ProgressBar className="mt-3" value={a.level.progress * 100} label="Progress to next level" />
          <p className="mt-2 text-xs text-muted-foreground">
            {a.level.xp.toLocaleString()} XP · {(a.level.next_level_xp - a.level.xp).toLocaleString()} XP to level {a.level.level + 1}
          </p>
        </Card>
        <Card className="p-5">
          <Stat label="Current streak" value={`${a.streak.current} day${a.streak.current === 1 ? "" : "s"}`} hint={`Longest ${a.streak.longest} · ${a.streak.freezes} freeze(s) — one is earned every 7 days`} icon={<Flame className="size-4 text-danger" />} />
        </Card>
        <Card className="p-5">
          <Stat label="Badges" value={`${earned} / ${a.achievements.length}`} icon={<Award className="size-4" />} />
        </Card>
      </div>

      {missions.data?.today && <MissionCard mission={missions.data.today} />}

      {missions.data && (
        <Card>
          <CardHeader title="This week's challenges" description="Weekly goals tuned to your weakest skill." />
          <CardBody className="grid gap-4 md:grid-cols-3">
            {missions.data.challenges.map((c) => (
              <div key={c.id} className={cn("rounded-xl border border-border p-4", c.completed && "bg-success-soft/50")}>
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium">{c.title}</p>
                  <Badge tone={c.completed ? "success" : "primary"}>+{c.xp_reward} XP</Badge>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{c.description}</p>
                <ProgressBar className="mt-3" value={(c.progress / c.target) * 100} tone={c.completed ? "success" : "primary"} label={c.title} />
                <p className="mt-1 text-xs text-muted-foreground">
                  {Math.min(c.progress, c.target)} / {c.target}
                </p>
              </div>
            ))}
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader title="Badges" />
        <CardBody className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {a.achievements.map((x) => {
            const Icon = ICONS[x.icon] ?? Award;
            return (
              <div key={x.code} className={cn("flex gap-3 rounded-xl border border-border p-3", !x.earned && "opacity-75")}>
                <div className={cn("grid size-11 shrink-0 place-items-center rounded-xl", x.earned ? "bg-warning-soft text-warning" : "bg-muted text-muted-foreground")}>
                  {x.earned ? <Icon className="size-5" aria-hidden /> : <Lock className="size-4" aria-hidden />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="font-medium">{x.name}</p>
                    <Badge tone={TIER_TONE[x.tier] ?? "default"}>{x.tier}</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">{x.description}</p>
                  {x.earned ? (
                    <p className="mt-1 text-xs text-success">Earned {formatDate(x.earned_at)}</p>
                  ) : (
                    <ProgressBar className="mt-2" value={x.progress * 100} label={`${x.name} progress`} />
                  )}
                </div>
              </div>
            );
          })}
        </CardBody>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Recent XP" />
          <CardBody>
            <ul className="space-y-2 text-sm">
              {a.recent_xp.map((x, i) => (
                <li key={i} className="flex items-center justify-between gap-3">
                  <span className="truncate">{x.description || x.reason}</span>
                  <span className="shrink-0 text-muted-foreground">
                    <span className="font-semibold text-primary">+{x.amount}</span> · {relativeTime(x.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
        {missions.data && (
          <Card>
            <CardHeader title="Mission history" />
            <CardBody>
              <ul className="space-y-2 text-sm">
                {missions.data.history.map((m) => (
                  <li key={m.day} className="flex items-center justify-between">
                    <span>{formatDate(m.day)}</span>
                    <Badge tone={m.status === "completed" ? "success" : "default"}>
                      {m.completed_tasks}/{m.total_tasks} tasks
                    </Badge>
                  </li>
                ))}
              </ul>
            </CardBody>
          </Card>
        )}
      </div>
    </div>
  );
}
