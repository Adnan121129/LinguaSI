"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useRef, useSyncExternalStore } from "react";

import { useMe, useUpdateProfile } from "@/hooks/use-me";
import { cn } from "@/lib/utils";

const OPTIONS = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
] as const;

const subscribe = () => () => {};

/** Light / Dark / System switch. The choice is stored locally and in the learner profile (synced across devices). */
export function ThemeToggle({ compact = false, persist = true }: { compact?: boolean; persist?: boolean }) {
  const { theme, setTheme } = useTheme();
  const mounted = useSyncExternalStore(subscribe, () => true, () => false);
  // Public pages (persist=false) have no signed-in learner to load.
  const { data: me } = useMe({ enabled: persist });
  const update = useUpdateProfile();
  const synced = useRef(false);

  // Adopt the theme saved on the server the first time the profile loads on this device.
  useEffect(() => {
    if (!persist || synced.current || !me) return;
    synced.current = true;
    if (me.profile.theme && me.profile.theme !== theme) setTheme(me.profile.theme);
  }, [me, persist, setTheme, theme]);

  const choose = (value: (typeof OPTIONS)[number]["value"]) => {
    setTheme(value);
    if (persist && me && me.profile.theme !== value) update.mutate({ theme: value });
  };

  return (
    <div role="radiogroup" aria-label="Theme" className="inline-flex rounded-xl border border-border bg-card p-0.5">
      {OPTIONS.map(({ value, label, icon: Icon }) => {
        const active = mounted && theme === value;
        return (
          <button
            key={value}
            role="radio"
            aria-checked={active}
            title={label}
            onClick={() => choose(value)}
            className={cn("flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium transition", active ? "bg-primary-soft text-primary" : "text-muted-foreground hover:text-foreground")}
          >
            <Icon className="size-3.5" aria-hidden />
            {!compact && label}
          </button>
        );
      })}
    </div>
  );
}
