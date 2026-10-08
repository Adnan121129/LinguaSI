"use client";

import { Award, CheckCircle2, Flame, Info, Sparkles, TriangleAlert, X, Zap } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";

import type { ActivityOutcome } from "@/lib/types";
import { cn } from "@/lib/utils";

type ToastTone = "info" | "success" | "warning" | "error" | "xp" | "achievement" | "streak";
export type Toast = { id: number; title: string; description?: string; tone: ToastTone };

type ToastContextValue = {
  toasts: Toast[];
  push: (toast: Omit<Toast, "id">) => void;
  dismiss: (id: number) => void;
  celebrate: (outcome: ActivityOutcome | null | undefined) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

const ICONS: Record<ToastTone, ReactNode> = {
  info: <Info className="size-4" />,
  success: <CheckCircle2 className="size-4" />,
  warning: <TriangleAlert className="size-4" />,
  error: <TriangleAlert className="size-4" />,
  xp: <Zap className="size-4" />,
  achievement: <Award className="size-4" />,
  streak: <Flame className="size-4" />,
};
const TONE_CLASSES: Record<ToastTone, string> = {
  info: "text-primary",
  success: "text-success",
  warning: "text-warning",
  error: "text-danger",
  xp: "text-primary",
  achievement: "text-warning",
  streak: "text-danger",
};

/** Builds the reward notifications shown after any activity (XP, level-ups, achievements, streaks). */
export function outcomeToasts(outcome: ActivityOutcome): Omit<Toast, "id">[] {
  const toasts: Omit<Toast, "id">[] = [];
  if (outcome.xp_gained > 0) {
    toasts.push({ tone: "xp", title: `+${outcome.xp_gained} XP`, description: outcome.xp_breakdown.map((x) => x.description).filter(Boolean).slice(0, 2).join(" · ") || undefined });
  }
  if (outcome.leveled_up) toasts.push({ tone: "achievement", title: `Level ${outcome.level}: ${outcome.level_title}`, description: "You reached a new level!" });
  for (const a of outcome.achievements) toasts.push({ tone: "achievement", title: `Achievement unlocked: ${a.name}`, description: a.description });
  if (outcome.streak_extended && outcome.streak > 1) toasts.push({ tone: "streak", title: `${outcome.streak}-day streak`, description: "Keep it going tomorrow." });
  if (outcome.mission_completed) toasts.push({ tone: "success", title: "Daily mission complete", description: "Bonus XP added." });
  return toasts;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => setToasts((all) => all.filter((t) => t.id !== id)), []);
  const push = useCallback(
    (toast: Omit<Toast, "id">) => {
      const id = nextId.current++;
      setToasts((all) => [...all.slice(-4), { ...toast, id }]);
      window.setTimeout(() => dismiss(id), toast.tone === "error" ? 8000 : 5000);
    },
    [dismiss],
  );
  const celebrate = useCallback((outcome: ActivityOutcome | null | undefined) => outcome && outcomeToasts(outcome).forEach(push), [push]);
  const value = useMemo(() => ({ toasts, push, dismiss, celebrate }), [toasts, push, dismiss, celebrate]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4 sm:inset-x-auto sm:right-4 sm:items-end">
        {toasts.map((toast) => (
          <div key={toast.id} role="status" className="animate-pop-in pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-2xl border border-border bg-card p-3.5 shadow-lg">
            <span className={cn("mt-0.5", TONE_CLASSES[toast.tone])}>{ICONS[toast.tone]}</span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold">{toast.title}</p>
              {toast.description && <p className="mt-0.5 text-xs text-muted-foreground">{toast.description}</p>}
            </div>
            <button onClick={() => dismiss(toast.id)} className="text-muted-foreground hover:text-foreground" aria-label="Dismiss notification">
              <X className="size-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside ToastProvider");
  return context;
}

export function SIActions({ outcome }: { outcome: ActivityOutcome | null | undefined }) {
  if (!outcome || (!outcome.si_actions.length && !outcome.mission_progress.length)) return null;
  return (
    <div className="rounded-2xl border border-primary/20 bg-primary-soft/60 p-4">
      <p className="flex items-center gap-2 text-sm font-semibold text-primary">
        <Sparkles className="size-4" aria-hidden /> What SI did next
      </p>
      <ul className="mt-2 space-y-1.5 text-sm text-foreground/90">
        {outcome.si_actions.map((action) => (
          <li key={action} className="flex gap-2">
            <span className="mt-2 size-1.5 shrink-0 rounded-full bg-primary" />
            {action}
          </li>
        ))}
        {outcome.mission_progress.map((line) => (
          <li key={line} className="flex gap-2 text-muted-foreground">
            <span className="mt-2 size-1.5 shrink-0 rounded-full bg-success" />
            {line}
          </li>
        ))}
      </ul>
    </div>
  );
}
