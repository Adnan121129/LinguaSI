import { screen, userEvent } from "@testing-library/react-native";

import { PracticeRunner } from "@/components/practice-runner";
import type { PracticeSet } from "@/lib/types";

import { jsonResponse, renderWithProviders } from "@/test/render";

jest.mock("@/lib/config", () => ({ API_URL: "https://api.test" }));
jest.mock("expo-router", () => ({ router: { replace: jest.fn(), navigate: jest.fn(), push: jest.fn() } }));

const PRACTICE: PracticeSet = {
  id: 7,
  kind: "revision",
  title: "5-minute Article Repair Challenge",
  description: "Fix the articles you keep getting wrong.",
  why: "You made 6 article mistakes in your last two essays.",
  focus: "articles",
  status: "active",
  items: [
    { id: "a", qtype: "multiple_choice", prompt: "She is ___ honest person.", options: ["a", "an", "the"], source: "bank", mistake_id: null },
    { id: "b", qtype: "gap_fill", prompt: "I studied at ___ University of Leeds.", options: null, source: "personal", mistake_id: 3 },
    { id: "c", qtype: "sentence_order", prompt: "Put the words in the correct order: sun / the / hot / is", options: null, source: "bank", mistake_id: null },
  ],
  total: 3,
  score: 0,
  accuracy: null,
  estimated_minutes: 5,
  results: [],
  created_at: "2026-10-08T10:00:00Z",
  completed_at: null,
};

const OUTCOME = {
  xp_gained: 15,
  xp_breakdown: [{ amount: 15, reason: "practice", description: "Repair challenge" }],
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

describe("PracticeRunner (mobile)", () => {
  it("collects every answer type, submits them and shows marked results", async () => {
    const fetchMock = jest.fn(async (_url: string, init: { body: string }) => {
      const answers = JSON.parse(init.body).answers;
      return jsonResponse({
        practice: {
          ...PRACTICE,
          status: "completed",
          score: 2,
          accuracy: 66.7,
          results: [
            { id: "a", correct: true, your_answer: answers.a, answer: "an", explanation: "'Honest' starts with a vowel sound." },
            { id: "b", correct: false, your_answer: answers.b, answer: "the", explanation: "Use 'the' with 'University of …'." },
            { id: "c", correct: true, your_answer: answers.c, answer: "the sun is hot", explanation: "" },
          ],
        },
        mastered_mistakes: [],
        outcome: OUTCOME,
      });
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const user = userEvent.setup();
    await renderWithProviders(<PracticeRunner practice={PRACTICE} />);

    expect(screen.getByText(PRACTICE.why)).toBeOnTheScreen();
    expect(screen.getByText("From your own work")).toBeOnTheScreen();
    await user.press(screen.getByRole("radio", { name: "an" }));
    await user.type(screen.getByLabelText("Your answer"), "a");
    for (const word of ["the", "sun", "is", "hot"]) await user.press(screen.getByRole("button", { name: word }));
    expect(screen.getByText("the sun is hot")).toBeOnTheScreen();
    expect(screen.getByText("3 of 3 answered")).toBeOnTheScreen();

    await user.press(screen.getByRole("button", { name: "Check my answers" }));

    expect(await screen.findByText("2 / 3")).toBeOnTheScreen();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("https://api.test/practice/sets/7/submit");
    expect(JSON.parse(init.body).answers).toEqual({ a: "an", b: "a", c: "the sun is hot" });
    expect(screen.getByText("Articles moved from 'struggling' to 'improving'")).toBeOnTheScreen();
    expect(screen.getByText("Use 'the' with 'University of …'.")).toBeOnTheScreen();
    expect(await screen.findByText("+15 XP")).toBeOnTheScreen();
  });

  it("lets the learner take words back before submitting", async () => {
    const user = userEvent.setup();
    await renderWithProviders(<PracticeRunner practice={{ ...PRACTICE, items: [PRACTICE.items[2]] }} />);
    await user.press(screen.getByRole("button", { name: "hot" }));
    await user.press(screen.getByRole("button", { name: "sun" }));
    expect(screen.getByText("hot sun")).toBeOnTheScreen();
    await user.press(screen.getByRole("button", { name: "Clear" }));
    expect(screen.getByText("Tap the words in the right order…")).toBeOnTheScreen();
  });
});
