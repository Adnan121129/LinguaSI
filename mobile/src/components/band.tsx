import { View } from "react-native";

import { ProgressBar, Text, type Tone } from "@/components/ui";
import { formatBand } from "@/lib/utils";

export const OFFICIAL_DISCLAIMER = "AI Estimated Bands are practice indicators, not official IELTS results, and do not guarantee any test, admission or immigration outcome.";

export function bandTone(band: number | null | undefined, target?: number): Tone {
  if (band === null || band === undefined) return "muted";
  if (target !== undefined && band >= target) return "success";
  if (band >= 7) return "success";
  if (band >= 5.5) return "primary";
  return "warning";
}

/** An AI estimated band - always labelled as an estimate, never as an official score. */
export function BandValue({ band, size = "md", target, label = "AI Estimated Band" }: { band: number | null | undefined; size?: "sm" | "md" | "lg"; target?: number; label?: string | null }) {
  const fontSize = size === "sm" ? 20 : size === "lg" ? 44 : 30;
  return (
    <View style={{ gap: 2 }}>
      {label ? <Text variant="label" tone="muted">{label}</Text> : null}
      <Text tone={bandTone(band, target)} style={{ fontSize, lineHeight: Math.round(fontSize * 1.15), fontWeight: "700", fontVariant: ["tabular-nums"] }}>
        {formatBand(band)}
      </Text>
    </View>
  );
}

export function CriterionBar({ label, band, comment }: { label: string; band: number | null; comment?: string }) {
  return (
    <View style={{ gap: 6 }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", gap: 8 }}>
        <Text variant="small" weight="600" style={{ flex: 1 }}>{label}</Text>
        <Text variant="small" weight="700" tone={bandTone(band)}>{band === null ? "Not assessed" : formatBand(band)}</Text>
      </View>
      <ProgressBar value={band === null ? 0 : (band / 9) * 100} />
      {comment ? <Text variant="caption" tone="muted">{comment}</Text> : null}
    </View>
  );
}
