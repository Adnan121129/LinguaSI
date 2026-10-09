import { afterEach, describe, expect, it, vi } from "vitest";

import { cn, formatBand, formatDate, formatDuration, percent, relativeTime, taskTypeLabel, titleCase, wordCount } from "@/lib/utils";

describe("formatting helpers", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("always shows bands with one decimal place", () => {
    expect(formatBand(6)).toBe("6.0");
    expect(formatBand(6.5)).toBe("6.5");
    expect(formatBand(null)).toBe("—");
    expect(formatBand(undefined)).toBe("—");
  });

  it("counts words like an examiner: contractions, hyphenated words and numbers count once", () => {
    expect(wordCount("It's a well-known fact, isn't it?")).toBe(6);
    expect(wordCount("In 2020, 45% of people…")).toBe(5);
    expect(wordCount("   ")).toBe(0);
  });

  it("shows calendar days on the same day in every timezone", () => {
    const original = process.env.TZ;
    process.env.TZ = "America/Los_Angeles";
    try {
      expect(formatDate("2026-10-08", { day: "numeric", month: "numeric" })).toBe("10/8");
    } finally {
      process.env.TZ = original;
    }
  });

  it("formats durations as minutes and seconds", () => {
    expect(formatDuration(65)).toBe("1:05");
    expect(formatDuration(3600)).toBe("60:00");
    expect(formatDuration(-3)).toBe("0:00");
  });

  it("describes recent times relative to now", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-08T12:00:00Z"));
    expect(relativeTime("2026-10-08T11:59:30Z")).toBe("just now");
    expect(relativeTime("2026-10-08T11:45:00Z")).toBe("15 minutes ago");
    expect(relativeTime("2026-10-08T09:00:00Z")).toBe("3 hours ago");
    expect(relativeTime("2026-10-07T12:00:00Z")).toBe("yesterday");
    expect(relativeTime(null)).toBe("");
  });

  it("labels question types, tasks and percentages for learners", () => {
    expect(titleCase("true_false_not_given")).toBe("True False Not Given");
    expect(taskTypeLabel("task1")).toBe("Task 1");
    expect(taskTypeLabel("task2")).toBe("Task 2");
    expect(taskTypeLabel("email")).toBe("General writing");
    expect(percent(66.6)).toBe("67%");
    expect(percent(null)).toBe("—");
  });

  it("lets later Tailwind classes override conflicting earlier ones", () => {
    expect(cn("w-full px-2", false, null, "w-auto")).toBe("px-2 w-auto");
  });
});
