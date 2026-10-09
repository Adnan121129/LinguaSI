import type { WritingErrorItem } from "@/lib/types";

export type Segment = { text: string; error?: WritingErrorItem };

/** Splits an essay into plain and highlighted segments using the error offsets from the evaluation (same rules as the web app). */
export function segmentText(text: string, errors: WritingErrorItem[]): Segment[] {
  const located = errors
    .filter((e) => e.start_offset !== null && e.end_offset !== null && e.end_offset > (e.start_offset ?? 0) && (e.end_offset ?? 0) <= text.length)
    .sort((a, b) => (a.start_offset ?? 0) - (b.start_offset ?? 0));
  const segments: Segment[] = [];
  let cursor = 0;
  for (const error of located) {
    const start = error.start_offset as number;
    const end = error.end_offset as number;
    if (start < cursor) continue; // overlapping detections: keep the first, list the rest below the essay
    if (start > cursor) segments.push({ text: text.slice(cursor, start) });
    segments.push({ text: text.slice(start, end), error });
    cursor = end;
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor) });
  return segments;
}
