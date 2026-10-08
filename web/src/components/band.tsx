import { cn, formatBand } from "@/lib/utils";

export function bandTone(band: number | null | undefined, target?: number) {
  if (band === null || band === undefined) return "text-muted-foreground";
  if (target !== undefined && band >= target) return "text-success";
  if (band >= 7) return "text-success";
  if (band >= 5.5) return "text-primary";
  return "text-warning";
}

/** An AI estimated band - always labelled as an estimate, never as an official score. */
export function BandValue({ band, size = "md", target, label = "AI Estimated Band" }: { band: number | null | undefined; size?: "sm" | "md" | "lg" | "xl"; target?: number; label?: string | null }) {
  const sizes = { sm: "text-lg", md: "text-2xl", lg: "text-4xl", xl: "text-6xl" };
  return (
    <div className="inline-flex flex-col">
      {label && <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</span>}
      <span className={cn("font-semibold tabular-nums leading-none", sizes[size], bandTone(band, target))}>{formatBand(band)}</span>
    </div>
  );
}

export function CriterionBar({ label, band, comment }: { label: string; band: number | null; comment?: string }) {
  const width = band === null ? 0 : (band / 9) * 100;
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className={cn("font-semibold tabular-nums", bandTone(band))}>{band === null ? "Not assessed" : formatBand(band)}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary" style={{ width: `${width}%` }} />
      </div>
      {comment && <p className="text-xs leading-relaxed text-muted-foreground">{comment}</p>}
    </div>
  );
}

export const OFFICIAL_DISCLAIMER = "AI Estimated Bands are practice indicators, not official IELTS results, and do not guarantee any test, admission or immigration outcome.";
