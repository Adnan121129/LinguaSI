"use client";

import { Fragment, useMemo } from "react";

import type { WritingErrorItem } from "@/lib/types";

type Segment = { text: string; error?: WritingErrorItem };

/** Splits the essay into plain and highlighted segments using the error offsets from the evaluation. */
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

export function HighlightedEssay({ text, errors, activeId, onSelect }: { text: string; errors: WritingErrorItem[]; activeId?: number | null; onSelect?: (error: WritingErrorItem) => void }) {
  const segments = useMemo(() => segmentText(text, errors), [text, errors]);
  return (
    <div className="whitespace-pre-wrap text-[15px] leading-8">
      {segments.map((segment, i) =>
        segment.error ? (
          <button
            key={i}
            type="button"
            className="mark-error"
            data-severity={segment.error.severity}
            data-active={activeId === segment.error.id}
            onClick={() => onSelect?.(segment.error!)}
            title={`${segment.error.corrected} — ${segment.error.explanation}`}
            aria-label={`Error: "${segment.text}". Suggested: "${segment.error.corrected}"`}
          >
            {segment.text}
          </button>
        ) : (
          <Fragment key={i}>{segment.text}</Fragment>
        ),
      )}
    </div>
  );
}
