import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SIActions, ToastProvider, outcomeToasts, useToast } from "@/components/providers/toast";
import type { ActivityOutcome } from "@/lib/types";

const QUIET: ActivityOutcome = {
  xp_gained: 0,
  xp_breakdown: [],
  total_xp: 1200,
  level: 4,
  level_title: "Explorer",
  leveled_up: false,
  streak: 1,
  streak_extended: false,
  achievements: [],
  mission_progress: [],
  mission_completed: false,
  si_actions: [],
};

const BIG_DAY: ActivityOutcome = {
  ...QUIET,
  xp_gained: 40,
  xp_breakdown: [
    { amount: 25, reason: "writing", description: "Essay evaluated" },
    { amount: 10, reason: "mission", description: "Mission task done" },
    { amount: 5, reason: "streak", description: "Streak bonus" },
  ],
  leveled_up: true,
  level: 5,
  level_title: "Achiever",
  achievements: [{ code: "first_essay", name: "First Essay", description: "Submitted your first essay.", icon: "pen", tier: "bronze", xp_reward: 20 }],
  streak: 6,
  streak_extended: true,
  mission_completed: true,
};

describe("outcomeToasts", () => {
  it("stays silent when an activity earned nothing", () => {
    expect(outcomeToasts(QUIET)).toEqual([]);
  });

  it("announces XP, level-ups, achievements, streaks and the finished mission", () => {
    const toasts = outcomeToasts(BIG_DAY);
    expect(toasts.map((t) => t.title)).toEqual(["+40 XP", "Level 5: Achiever", "Achievement unlocked: First Essay", "6-day streak", "Daily mission complete"]);
    expect(toasts[0].description).toBe("Essay evaluated · Mission task done");
  });

  it("does not celebrate the first day of a streak", () => {
    expect(outcomeToasts({ ...QUIET, streak: 1, streak_extended: true })).toEqual([]);
  });
});

function Celebrate({ outcome }: { outcome: ActivityOutcome }) {
  const { celebrate } = useToast();
  return <button onClick={() => celebrate(outcome)}>Finish activity</button>;
}

describe("ToastProvider", () => {
  it("shows reward notifications that can be dismissed", () => {
    render(
      <ToastProvider>
        <Celebrate outcome={{ ...QUIET, xp_gained: 15, xp_breakdown: [{ amount: 15, reason: "practice", description: "Practice set" }] }} />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Finish activity" }));
    expect(screen.getByRole("status")).toHaveTextContent("+15 XP");
    fireEvent.click(screen.getByRole("button", { name: "Dismiss notification" }));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});

describe("SIActions", () => {
  it("explains what SI changed after the activity", () => {
    render(<SIActions outcome={{ ...QUIET, si_actions: ["Added 3 article sentences to tomorrow's revision"], mission_progress: ["Mission: 2 of 3 tasks done"] }} />);
    expect(screen.getByText("What SI did next")).toBeInTheDocument();
    expect(screen.getByText("Added 3 article sentences to tomorrow's revision")).toBeInTheDocument();
    expect(screen.getByText("Mission: 2 of 3 tasks done")).toBeInTheDocument();
  });

  it("renders nothing when there is nothing to report", () => {
    const { container } = render(<SIActions outcome={QUIET} />);
    expect(container).toBeEmptyDOMElement();
  });
});
