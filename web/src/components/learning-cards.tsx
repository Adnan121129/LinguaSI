"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, ChevronDown, CircleCheck, Clock, Lightbulb, Sparkles, Target, X, Zap } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Badge, Card, CardBody, CardHeader, ProgressBar, buttonClasses } from "@/components/ui";
import { api } from "@/lib/api";
import type { Mission, Recommendation, SIEvent } from "@/lib/types";
import { cn, relativeTime } from "@/lib/utils";

export function MissionCard({ mission }: { mission: Mission }) {
  const done = mission.completed_tasks;
  return (
    <Card>
      <CardHeader
        icon={<Target className="size-4" />}
        title={mission.title}
        description={mission.summary}
        action={
          <Badge tone={mission.status === "completed" ? "success" : "primary"}>
            {done}/{mission.total_tasks} done
          </Badge>
        }
      />
      <CardBody className="space-y-3">
        {mission.tasks.map((task) => (
          <div key={task.id} className={cn("rounded-xl border border-border p-3.5", task.completed && "bg-success-soft/50")}>
            <div className="flex items-start gap-3">
              <span className={cn("mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border", task.completed ? "border-success bg-success text-white" : "border-border")}>
                {task.completed && <Check className="size-3" aria-hidden />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className={cn("font-medium", task.completed && "text-muted-foreground line-through")}>{task.title}</p>
                  <span className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Clock className="size-3" aria-hidden /> {task.minutes} min
                    <Zap className="size-3" aria-hidden /> {task.xp} XP
                  </span>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{task.why}</p>
                {task.target > 1 && <ProgressBar className="mt-2" value={(task.progress / task.target) * 100} tone={task.completed ? "success" : "primary"} label={`${task.title} progress`} />}
              </div>
              {!task.completed && (
                <Link href={task.route} className={buttonClasses("secondary", "sm", "shrink-0")} aria-label={`Start: ${task.title}`}>
                  Start
                </Link>
              )}
            </div>
          </div>
        ))}
        {mission.status === "completed" ? (
          <p className="flex items-center gap-2 text-sm font-medium text-success">
            <CircleCheck className="size-4" /> Mission complete — {mission.bonus_xp} bonus XP earned.
          </p>
        ) : (
          <p className="text-xs text-muted-foreground">Finish every task for {mission.bonus_xp} bonus XP.</p>
        )}
      </CardBody>
    </Card>
  );
}

export function RecommendationCard({ rec, primary = false }: { rec: Recommendation; primary?: boolean }) {
  const [open, setOpen] = useState(primary);
  const queryClient = useQueryClient();
  const dismiss = useMutation({
    mutationFn: () => api(`/recommendations/${rec.id}/dismiss`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });
  return (
    <div className={cn("rounded-2xl border p-4", primary ? "border-primary/30 bg-primary-soft/50" : "border-border bg-card")}>
      <div className="flex items-start justify-between gap-3">
        <div>
          {primary && (
            <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-primary">
              <Sparkles className="size-3.5" aria-hidden /> SI recommends
            </p>
          )}
          <p className="font-semibold">{rec.title}</p>
          <p className="mt-1 text-sm text-muted-foreground">{rec.description}</p>
        </div>
        <button onClick={() => dismiss.mutate()} disabled={dismiss.isPending} className="rounded-lg p-1 text-muted-foreground hover:bg-muted" aria-label={`Dismiss recommendation: ${rec.title}`}>
          <X className="size-4" />
        </button>
      </div>
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open} className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-primary">
        <Lightbulb className="size-4" aria-hidden /> Why this?
        <ChevronDown className={cn("size-4 transition", open && "rotate-180")} aria-hidden />
      </button>
      {open && <p className="mt-2 rounded-xl bg-card/70 p-3 text-sm">{rec.why}</p>}
      <div className="mt-3 flex items-center gap-3">
        {rec.route && (
          <Link href={rec.route} className={buttonClasses(primary ? "primary" : "secondary", "sm")}>
            Start <ArrowRight className="size-3.5" />
          </Link>
        )}
        <span className="text-xs text-muted-foreground">About {rec.estimated_minutes} min</span>
      </div>
    </div>
  );
}

export function SIFeed({ events }: { events: SIEvent[] }) {
  if (!events.length) return <p className="text-sm text-muted-foreground">SI will explain what it changes after your first activity.</p>;
  return (
    <ol className="space-y-4">
      {events.map((event) => (
        <li key={event.id} className="relative pl-5">
          <span className="absolute left-0 top-1.5 size-2 rounded-full bg-primary" aria-hidden />
          <p className="text-sm font-medium">{event.title}</p>
          <p className="text-sm text-muted-foreground">{event.detail}</p>
          {event.actions.length > 0 && (
            <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
              {event.actions.slice(0, 3).map((a) => (
                <li key={a}>→ {a}</li>
              ))}
            </ul>
          )}
          <p className="mt-1 text-xs text-muted-foreground">{relativeTime(event.created_at)}</p>
        </li>
      ))}
    </ol>
  );
}
