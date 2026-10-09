import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HighlightedEssay, segmentText } from "@/components/writing/highlighted-essay";
import type { WritingErrorItem } from "@/lib/types";

const TEXT = "Many people thinks that cities is crowded.";

function errorAt(id: number, phrase: string, corrected: string, extra: Partial<WritingErrorItem> = {}): WritingErrorItem {
  const start = TEXT.indexOf(phrase);
  return {
    id,
    category: "grammar",
    subcategory: "subject_verb_agreement",
    original: phrase,
    corrected,
    explanation: "A plural subject takes a plural verb.",
    severity: "medium",
    start_offset: start,
    end_offset: start + phrase.length,
    repeated: false,
    mistake_id: null,
    source: "rules",
    ...extra,
  };
}

describe("segmentText", () => {
  it("splits the essay into plain text and highlighted errors in reading order", () => {
    const thinks = errorAt(1, "thinks", "think");
    const is = errorAt(2, " is ", " are ");
    const segments = segmentText(TEXT, [is, thinks]);
    expect(segments.map((s) => s.text).join("")).toBe(TEXT);
    expect(segments.filter((s) => s.error).map((s) => s.error!.id)).toEqual([1, 2]);
    expect(segments[0]).toEqual({ text: "Many people " });
  });

  it("keeps the first of two overlapping detections so no text is duplicated", () => {
    const segments = segmentText(TEXT, [errorAt(1, "thinks", "think"), errorAt(2, "thinks that", "think that")]);
    expect(segments.map((s) => s.text).join("")).toBe(TEXT);
    expect(segments.filter((s) => s.error)).toHaveLength(1);
  });

  it("ignores errors without usable offsets", () => {
    const unlocated = { ...errorAt(1, "thinks", "think"), start_offset: null, end_offset: null };
    const outOfRange = { ...errorAt(2, "crowded", "crowded"), end_offset: TEXT.length + 5 };
    const empty = { ...errorAt(3, "cities", "cities"), end_offset: TEXT.indexOf("cities") };
    expect(segmentText(TEXT, [unlocated, outOfRange, empty])).toEqual([{ text: TEXT }]);
  });
});

describe("HighlightedEssay", () => {
  it("lets the learner open an error's explanation from the highlighted text", () => {
    const thinks = errorAt(1, "thinks", "think");
    const onSelect = vi.fn();
    render(<HighlightedEssay text={TEXT} errors={[thinks]} activeId={1} onSelect={onSelect} />);
    const mark = screen.getByRole("button", { name: 'Error: "thinks". Suggested: "think"' });
    expect(mark).toHaveAttribute("data-active", "true");
    fireEvent.click(mark);
    expect(onSelect).toHaveBeenCalledWith(thinks);
  });

  it("marks low-severity issues differently from errors", () => {
    render(<HighlightedEssay text={TEXT} errors={[errorAt(1, "crowded", "overcrowded", { severity: "low", category: "vocabulary" })]} />);
    expect(screen.getByRole("button", { name: /crowded/ })).toHaveAttribute("data-severity", "low");
  });
});
