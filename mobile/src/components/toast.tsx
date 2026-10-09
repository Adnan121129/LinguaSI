import { Award, CheckCircle2, Flame, Info, Sparkles, TriangleAlert, X, Zap, type LucideIcon } from "lucide-react-native";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Pressable, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Text, toneColors, type Tone } from "@/components/ui";
import { useTheme } from "@/lib/theme";
import type { ActivityOutcome } from "@/lib/types";

type ToastTone = "info" | "success" | "warning" | "error" | "xp" | "achievement" | "streak";
export type Toast = { id: number; title: string; description?: string; tone: ToastTone };

const STYLE: Record<ToastTone, { icon: LucideIcon; tone: Tone }> = {
  info: { icon: Info, tone: "primary" },
  success: { icon: CheckCircle2, tone: "success" },
  warning: { icon: TriangleAlert, tone: "warning" },
  error: { icon: TriangleAlert, tone: "danger" },
  xp: { icon: Zap, tone: "primary" },
  achievement: { icon: Award, tone: "warning" },
  streak: { icon: Flame, tone: "danger" },
};

/** Reward notifications after any activity (XP, level-ups, achievements, streaks). Same rules as the web app. */
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

type ToastContextValue = {
  push: (toast: Omit<Toast, "id">) => void;
  celebrate: (outcome: ActivityOutcome | null | undefined) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();

  const dismiss = useCallback((id: number) => {
    setToasts((all) => all.filter((t) => t.id !== id));
    clearTimeout(timers.current.get(id));
    timers.current.delete(id);
  }, []);

  const push = useCallback(
    (toast: Omit<Toast, "id">) => {
      const id = nextId.current++;
      setToasts((all) => [...all.slice(-2), { ...toast, id }]);
      timers.current.set(
        id,
        setTimeout(() => dismiss(id), toast.tone === "error" ? 7000 : 4500),
      );
    },
    [dismiss],
  );

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach(clearTimeout);
  }, []);

  const celebrate = useCallback((outcome: ActivityOutcome | null | undefined) => outcome && outcomeToasts(outcome).forEach(push), [push]);
  const value = useMemo(() => ({ push, celebrate }), [push, celebrate]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <View pointerEvents="box-none" style={{ position: "absolute", top: insets.top + 8, left: 12, right: 12, gap: 8 }}>
        {toasts.map((toast) => {
          const { icon: Icon, tone } = STYLE[toast.tone];
          return (
            <View
              key={toast.id}
              accessibilityRole="alert"
              accessibilityLiveRegion="polite"
              style={{
                flexDirection: "row",
                gap: 10,
                alignItems: "flex-start",
                backgroundColor: colors.card,
                borderColor: colors.border,
                borderWidth: 1,
                borderRadius: 16,
                padding: 12,
                shadowColor: "#000",
                shadowOpacity: 0.12,
                shadowRadius: 12,
                shadowOffset: { width: 0, height: 4 },
                elevation: 4,
              }}
            >
              <Icon size={18} color={toneColors(colors, tone).fg} style={{ marginTop: 1 }} />
              <View style={{ flex: 1, gap: 2 }}>
                <Text weight="600">{toast.title}</Text>
                {toast.description ? <Text variant="small" tone="muted">{toast.description}</Text> : null}
              </View>
              <Pressable onPress={() => dismiss(toast.id)} accessibilityRole="button" accessibilityLabel="Dismiss notification" hitSlop={10}>
                <X size={16} color={colors.mutedForeground} />
              </Pressable>
            </View>
          );
        })}
      </View>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside ToastProvider");
  return context;
}

/** "What SI did next": the profile, plan and revision changes an activity triggered. */
export function SIActions({ outcome }: { outcome: ActivityOutcome | null | undefined }) {
  const { colors } = useTheme();
  if (!outcome || (!outcome.si_actions.length && !outcome.mission_progress.length)) return null;
  return (
    <View style={{ borderRadius: 16, borderWidth: 1, borderColor: colors.primarySoft, backgroundColor: colors.primarySoft, padding: 14, gap: 8 }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
        <Sparkles size={16} color={colors.primary} />
        <Text weight="600" tone="primary">What SI did next</Text>
      </View>
      {outcome.si_actions.map((action) => (
        <View key={action} style={{ flexDirection: "row", gap: 8 }}>
          <View style={{ width: 6, height: 6, borderRadius: 3, marginTop: 8, backgroundColor: colors.primary }} />
          <Text variant="small" style={{ flex: 1 }}>{action}</Text>
        </View>
      ))}
      {outcome.mission_progress.map((line) => (
        <View key={line} style={{ flexDirection: "row", gap: 8 }}>
          <View style={{ width: 6, height: 6, borderRadius: 3, marginTop: 8, backgroundColor: colors.success }} />
          <Text variant="small" tone="muted" style={{ flex: 1 }}>{line}</Text>
        </View>
      ))}
    </View>
  );
}
