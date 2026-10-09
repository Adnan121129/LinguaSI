import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { PracticeRunner } from "@/components/practice/practice-runner";
import type { ActivityOutcome, PracticeSet, PracticeSubmitResponse } from "@/lib/types";
import { jsonResponse, mockFetch, renderWithProviders } from "@/test/render";

const PRACTICE: PracticeSet = {
  id: 7,
  kind: "repair_challenge",
  title: "5-minute Article Repair Challenge",
  description: "Fix the articles you keep getting wrong.",
  why: "You made 6 article mistakes in your last two essays.",
  focus: "articles",
  status: "active",
  items: [
    { id: "a", qtype: "multiple_choice", prompt: "She is ___ honest person.", options: ["a", "an", "the"], source: "bank", mistake_id: null },
    { id: "b", qtype: "gap_fill", prompt: "I studied at ___ University of Leeds.", options: null, source: "personal", mistake_id: 3 },
    { id: "c", qtype: "sentence_order", prompt: "Put the words in the correct order: sun / the / hot / is", options: null, source: "bank", mistake_id: null },
    { id: "d", qtype: "error_correction", prompt: "Correct the error: He is best student in the class.", options: null, source: "bank", mistake_id: null },
  ],
  total: 4,
  score: 0,
  accuracy: null,
  estimated_minutes: 5,
  results: [],
  created_at: "2026-10-08T10:00:00Z",
  completed_at: null,
};

const OUTCOME: ActivityOutcome = {
  xp_gained: 20,
  xp_breakdown: [{ amount: 20, reason: "practice", description: "Repair challenge" }],
  total_xp: 900,
  level: 3,
  level_title: "Explorer",
  leveled_up: false,
  streak: 1,
  streak_extended: false,
  achievements: [],
  mission_progress: [],
  mission_completed: false,
  si_actions: ["Articles moved from 'struggling' to 'improving'"],
};

function submitted(answers: Record<string, string>): PracticeSubmitResponse {
  return {
    practice: {
      ...PRACTICE,
      status: "completed",
      score: 3,
      accuracy: 75,
      completed_at: "2026-10-08T10:05:00Z",
      results: [
        { id: "a", correct: true, your_answer: answers.a, answer: "an", explanation: "'Honest' starts with a vowel sound." },
        { id: "b", correct: true, your_answer: answers.b, answer: "the", explanation: "Use 'the' with 'University of …'." },
        { id: "c", correct: true, your_answer: answers.c, answer: "the sun is hot", explanation: "" },
        { id: "d", correct: false, your_answer: answers.d, answer: "He is the best student in the class.", explanation: "Superlatives take 'the'." },
      ],
    },
    mastered_mistakes: [3],
    outcome: OUTCOME,
  };
}

describe("PracticeRunner", () => {
  it("collects every answer type, submits them and shows marked results", async () => {
    const user = userEvent.setup();
    const fetch = mockFetch((_url, init) => jsonResponse(submitted(JSON.parse(String(init.body)).answers)));
    renderWithProviders(<PracticeRunner practice={PRACTICE} />);

    expect(screen.getByText(PRACTICE.why)).toBeInTheDocument();
    expect(screen.getByText("From your own work")).toBeInTheDocument();
    expect(screen.getByText("0 of 4 answered")).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "an" }));
    const [gap, correction] = screen.getAllByLabelText("Your answer");
    await user.type(gap, "the");
    for (const word of ["the", "sun", "is", "hot"]) await user.click(screen.getByRole("button", { name: word }));
    expect(screen.getByText("the sun is hot")).toBeInTheDocument();
    await user.type(correction, "He is best student in the class.");
    expect(screen.getByText("4 of 4 answered")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Check my answers" }));

    expect(await screen.findByText("3 / 4")).toBeInTheDocument();
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("/api/backend/practice/sets/7/submit");
    const body = JSON.parse(String(init?.body));
    expect(body.answers).toEqual({ a: "an", b: "the", c: "the sun is hot", d: "He is best student in the class." });
    expect(body.duration_seconds).toBeGreaterThanOrEqual(0);

    expect(screen.getByText("75% correct")).toBeInTheDocument();
    expect(screen.getByText("1 mistake(s) mastered")).toBeInTheDocument();
    expect(screen.getByText("Articles moved from 'struggling' to 'improving'")).toBeInTheDocument();
    expect(screen.getByText("He is the best student in the class.")).toBeInTheDocument();
    expect(screen.getByText("Superlatives take 'the'.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("+20 XP"));
    expect(screen.getByRole("link", { name: "Back to My Mistakes" })).toHaveAttribute("href", "/mistakes");
  });

  it("lets the learner undo a word order before submitting", async () => {
    const user = userEvent.setup();
    renderWithProviders(<PracticeRunner practice={{ ...PRACTICE, items: [PRACTICE.items[2]] }} />);
    const sentence = () => screen.getByText((_, el) => el?.getAttribute("aria-live") === "polite" && el.tagName === "DIV" && !el.className.includes("fixed"));
    await user.click(screen.getByRole("button", { name: "hot" }));
    await user.click(screen.getByRole("button", { name: "sun" }));
    expect(sentence()).toHaveTextContent(/^hot sun$/);
    await user.click(screen.getByRole("button", { name: "sun" }));
    expect(sentence()).toHaveTextContent(/^hot$/);
    await user.click(screen.getByRole("button", { name: "Clear" }));
    expect(screen.getByText("Tap the words in the right order…")).toBeInTheDocument();
    expect(screen.getByText("0 of 1 answered")).toBeInTheDocument();
  });

  it("keeps the answers and offers a retry when submission fails", async () => {
    const user = userEvent.setup();
    let calls = 0;
    mockFetch((_url, init) => {
      calls += 1;
      if (calls === 1) return jsonResponse({ error: { code: "service_unavailable", message: "We couldn't check your answers right now. Your answers are kept - try again." } }, 503);
      return jsonResponse(submitted(JSON.parse(String(init.body)).answers));
    });
    renderWithProviders(<PracticeRunner practice={{ ...PRACTICE, items: [PRACTICE.items[0]] }} />);
    await user.click(screen.getByRole("radio", { name: "an" }));
    await user.click(screen.getByRole("button", { name: "Check my answers" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("We couldn't check your answers right now.");
    expect(screen.getByRole("radio", { name: "an" })).toBeChecked();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("3 / 4")).toBeInTheDocument();
  });

  it("shows the results of an already completed set without asking again", () => {
    renderWithProviders(<PracticeRunner practice={submitted({ a: "an", b: "the", c: "the sun is hot", d: "x" }).practice} exit={{ href: "/lab", label: "Back to the Lab" }} />);
    expect(screen.getByText("3 / 4")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Check my answers" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to the Lab" })).toHaveAttribute("href", "/lab");
  });
});
