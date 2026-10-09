import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useColorScheme } from "react-native";

import { prefs } from "@/lib/storage";

export type ThemePreference = "light" | "dark" | "system";
export type Scheme = "light" | "dark";

// Same design tokens as the web app (web/src/app/globals.css), including the validated chart palette.
const light = {
  background: "#f7f8fc",
  foreground: "#0f172a",
  card: "#ffffff",
  muted: "#eef1f7",
  mutedForeground: "#5b6478",
  border: "#e2e6ef",
  primary: "#4f46e5",
  primaryForeground: "#ffffff",
  primarySoft: "#eef0ff",
  accent: "#0ea5e9",
  accentSoft: "#e6f6fd",
  success: "#059669",
  successSoft: "#e7f8f1",
  warning: "#d97706",
  warningSoft: "#fdf4e3",
  danger: "#dc2626",
  dangerSoft: "#fdecec",
  series: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"],
  seq: ["#eef1f7", "#cde2fb", "#9ec5f4", "#5598e7", "#256abf", "#104281"],
  seqInk: "#ffffff", // label colour on the strongest cells
  grid: "#e8ebf2",
  axisText: "#6b7385",
  overlay: "rgba(15, 23, 42, 0.45)",
};

const dark: typeof light = {
  background: "#0b1020",
  foreground: "#e6e9f2",
  card: "#121a2e",
  muted: "#1a2338",
  mutedForeground: "#98a2b8",
  border: "#243049",
  primary: "#818cf8",
  primaryForeground: "#0b1020",
  primarySoft: "#1e2350",
  accent: "#38bdf8",
  accentSoft: "#0e2a3d",
  success: "#34d399",
  successSoft: "#0f2e25",
  warning: "#fbbf24",
  warningSoft: "#33270c",
  danger: "#f87171",
  dangerSoft: "#3a1717",
  series: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181"],
  seq: ["#1a2338", "#104281", "#1c5cab", "#2a78d6", "#5598e7", "#9ec5f4"],
  seqInk: "#0b1020",
  grid: "#222c42",
  axisText: "#8e98ae",
  overlay: "rgba(0, 0, 0, 0.6)",
};

export type Colors = typeof light;
export const PALETTES: Record<Scheme, Colors> = { light, dark };

type ThemeContextValue = {
  scheme: Scheme;
  colors: Colors;
  preference: ThemePreference;
  setPreference: (preference: ThemePreference) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);
const PREFERENCE_KEY = "theme";

/** Light / Dark / System. The choice is applied instantly, saved on the device and (by the caller) to the profile. */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const system = useColorScheme();
  const [preference, setPreferenceState] = useState<ThemePreference>("system");

  useEffect(() => {
    prefs.get(PREFERENCE_KEY).then((stored) => {
      if (stored === "light" || stored === "dark" || stored === "system") setPreferenceState(stored);
    });
  }, []);

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next);
    prefs.set(PREFERENCE_KEY, next);
  }, []);

  const scheme: Scheme = preference === "system" ? (system === "dark" ? "dark" : "light") : preference;
  const value = useMemo(() => ({ scheme, colors: PALETTES[scheme], preference, setPreference }), [scheme, preference, setPreference]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used inside ThemeProvider");
  return context;
}
