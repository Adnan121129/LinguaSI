import { segmentText } from "@/lib/segments";
import type { WritingErrorItem } from "@/lib/types";

const TEXT = "Many people thinks that cities is crowded.";
const error = (id: number, phrase: string): WritingErrorItem => {
  const start = TEXT.indexOf(phrase);
  return { id, category: "grammar", subcategory: "sva", original: phrase, corrected: phrase, explanation: "", severity: "medium", start_offset: start, end_offset: start + phrase.length, repeated: false, mistake_id: null, source: "rules" };
};

describe("segmentText", () => {
  it("splits the essay in reading order without losing text", () => {
    const segments = segmentText(TEXT, [error(2, " is "), error(1, "thinks")]);
    expect(segments.map((s) => s.text).join("")).toBe(TEXT);
    expect(segments.filter((s) => s.error).map((s) => s.error!.id)).toEqual([1, 2]);
  });

  it("drops overlapping and unlocated errors", () => {
    const unlocated = { ...error(3, "crowded"), start_offset: null, end_offset: null };
    const segments = segmentText(TEXT, [error(1, "thinks"), error(2, "thinks that"), unlocated]);
    expect(segments.filter((s) => s.error)).toHaveLength(1);
  });
});
