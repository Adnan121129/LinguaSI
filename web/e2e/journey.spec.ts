import { expect, test, type Locator, type Page } from "@playwright/test";

// The acceptance journey: a brand-new learner goes through every core module once, in Mock AI Mode,
// then comes back in a fresh browser and finds their progress and theme where they left them.

// An essay with deliberate, common learner errors so the evaluation has mistakes to record.
const ESSAY = `Nowadays many people believe that technology has changed the way we learn. In my opinion, the benefits of online learning are greater than the drawbacks, although good teachers are still essential.

Firstly, students can find informations about almost any subject in a few seconds. A student who wants to discuss about a difficult topic can join an online forum and ask a important question to experts from other countries. This makes learning faster and more flexible, especially for adults who work full time and cannot attend classes during the day.

Secondly, technology let students to study at their own pace. For example, my brother watches recorded lectures in the evening, and he can pause the video when he do not understand something. Most of people also enjoy to use educational apps because they feel like games and reward progress with points and badges.

However, there are some disadvantages. Some learners spend too much time on social media and they can to lose focus easily. In addition, not every family can afford a fast internet connection, so online learning may increase inequality between rich and poor students in the same city.

In conclusion, although online learning has some problems, I believe it brings more advantages than disadvantages. Governments should invest on cheaper internet access and schools should teach students how to manage their time, so that everyone can benefit from these new opportunities and continue learning throughout their lives.`;

const DIAGNOSTIC_WRITING = `I think working from home has advantages and disadvantages. People save a lot of time because they do not travel to the office every day, and they can spend this time with their family. However, some workers feels lonely and it is difficult to separate work and free time. In my opinion, the best solution is a mix of both, for example two days at home and three days in the office, because people need contact with colleagues but they also need flexibility in their lives.`;

const SPOKEN_ANSWERS = [
  "I live in a small apartment near the city centre with my two sisters. I really like it because it is close to my university and there are many cafes nearby, although it can be quite noisy at the weekend when people go out.",
  "At the moment I am studying computer science at university. I chose this subject because I have always enjoyed solving problems, and I think technology will create a lot of good jobs in the future. The hardest part for me is mathematics.",
  "In my free time I usually play football with my friends or read novels. Recently I started learning to cook, because I want to eat more healthily and save some money. My favourite dish to make is a simple vegetable curry with rice.",
  "Yes, I think so. When I was a child I spent most of my time outdoors, but now I spend many hours in front of a screen, so I try to go for a walk every evening to relax and clear my head before I go to sleep.",
];

const main = (page: Page) => page.getByRole("main");

/** Answers every question in the main content: first option, a dropdown choice or a short typed answer. */
async function answerAll(items: Locator, typed = "the") {
  await expect(items.first()).toBeVisible();
  for (const item of await items.all()) {
    const radios = item.getByRole("radio");
    const select = item.locator("select");
    const textbox = item.getByRole("textbox");
    const words = item.locator('button[aria-pressed="false"]');
    if (await radios.count()) await radios.first().check();
    else if (await select.count()) await select.selectOption({ index: 1 });
    else if (await textbox.count()) await textbox.fill(typed);
    else while (await words.count()) await words.first().click(); // sentence building: tap every word
  }
}

/** The recorder's keyboard path: the answer is typed (and labelled as typed, so it is never scored for pronunciation). */
async function typeSpokenAnswer(page: Page, text: string, submit: string) {
  await page.getByRole("button", { name: "Type instead" }).first().click();
  await page.getByLabel("Your answer").fill(text);
  await page.getByRole("button", { name: submit }).click();
}

test("a new learner completes the core journey and picks it up again later", async ({ browser }) => {
  const learner = { name: "Journey Tester", email: `journey-${Date.now()}@example.com`, password: "Journey-test-2026" };
  const context = await browser.newContext({ colorScheme: "light" });
  const page = await context.newPage();

  await test.step("register", async () => {
    await page.goto("/register");
    await page.getByLabel("Name").fill(learner.name);
    await page.getByLabel("Email").fill(learner.email);
    await page.getByLabel("Password").fill(learner.password);
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page).toHaveURL(/\/onboarding$/);
  });

  await test.step("complete the learning profile", async () => {
    await expect(page.getByRole("heading", { name: "Let's personalise LinguaSI for you", exact: true })).toBeVisible();
    await page.getByRole("button", { name: /Prepare for IELTS/ }).click();
    await page.getByLabel("Target band").selectOption("7");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByRole("button", { name: /^Intermediate/ }).click();
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByRole("button", { name: /^Balanced/ }).click();
    await page.getByRole("button", { name: "Take the 15-minute diagnostic" }).click();
    await expect(page).toHaveURL(/\/onboarding\/diagnostic$/);
  });

  await test.step("take the diagnostic and get an estimated level", async () => {
    for (const section of ["Vocabulary", "Grammar", "Reading", "Listening"]) {
      await expect(page.getByRole("heading", { level: 1, name: section })).toBeVisible();
      await answerAll(main(page).locator("ol > li"));
      await page.getByRole("button", { name: "Next section" }).click();
    }
    await expect(page.getByRole("heading", { level: 1, name: "Writing" })).toBeVisible();
    await page.getByLabel("Your writing").fill(DIAGNOSTIC_WRITING);
    await page.getByRole("button", { name: "Next section" }).click();

    await expect(page.getByRole("heading", { level: 1, name: "Speaking" })).toBeVisible();
    let answered = 0;
    while (await page.getByRole("button", { name: "Type instead" }).count()) {
      await typeSpokenAnswer(page, SPOKEN_ANSWERS[answered % SPOKEN_ANSWERS.length], "Save answer");
      answered += 1;
      await expect(page.getByText("Answer saved")).toHaveCount(answered);
    }
    await page.getByRole("button", { name: "See my results" }).click();

    await expect(page.getByRole("heading", { name: "Your starting point", exact: true })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("AI Estimated Level", { exact: true })).toBeVisible();
    await expect(page.getByText(/not an official IELTS result/i)).toBeVisible();
    await page.getByRole("link", { name: "Go to my dashboard" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
  });

  await test.step("see a personalised recommendation on the dashboard", async () => {
    await expect(page.getByText("SI recommends", { exact: true })).toBeVisible();
    // The main recommendation explains itself ("Why this?" is open by default).
    await expect(page.getByRole("button", { name: "Why this?" }).first()).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByText("Take the 15-minute diagnostic")).toHaveCount(0);
  });

  let submissionUrl = "";
  await test.step("write an essay and get an AI evaluation", async () => {
    await page.goto("/writing");
    await page.getByLabel("Task type").selectOption("task2");
    await page.getByRole("button", { name: "Start in tutor mode" }).first().click();
    await expect(page).toHaveURL(/\/writing\/\d+$/);
    submissionUrl = page.url();
    await page.getByLabel("Your response").fill(ESSAY);
    await page.getByRole("button", { name: "Submit for evaluation" }).click();

    await expect(page.getByRole("heading", { name: "Writing evaluation", exact: true })).toBeVisible({ timeout: 90_000 });
    await expect(page.getByText("Criteria", { exact: true })).toBeVisible();
    await expect(page.getByText(/AI Estimated/).first()).toBeVisible();
    // Errors are highlighted in the learner's own text.
    await expect(page.locator(".mark-error", { hasText: /informations/i }).first()).toBeVisible();
  });

  await test.step("find the mistakes in My Mistakes and practise one", async () => {
    await page.goto("/mistakes");
    await expect(page.getByRole("heading", { name: "My Mistakes", exact: true })).toBeVisible();
    const mistake = main(page)
      .getByRole("button")
      .filter({ has: page.locator(".mark-error", { hasText: /informations/i }) })
      .first();
    await mistake.click();
    await page.getByRole("button", { name: "Mini practice" }).click();

    await expect(page).toHaveURL(/\/practice\/\d+$/, { timeout: 30_000 });
    await expect(page.getByText("From your own work").first()).toBeVisible();
    await answerAll(main(page).locator("ol > li"));
    await page.getByRole("button", { name: "Check my answers" }).click();
    await expect(page.getByText(/^\d+% correct$/)).toBeVisible();
    await expect(page.getByRole("link", { name: "Back to My Mistakes" })).toBeVisible();
  });

  await test.step("review vocabulary", async () => {
    await page.goto("/vocabulary");
    const done = page.getByText("Session complete");
    for (let i = 0; i < 40; i++) {
      const card = main(page);
      const radios = card.getByRole("radio");
      const sentence = card.getByLabel("Your sentence");
      await expect(card.getByRole("button", { name: "Check", exact: true })).toBeVisible();
      if (await radios.count()) await radios.first().check();
      else if (await sentence.count()) await sentence.fill("I try to use this new word in a sentence about my studies every day.");
      else await card.getByLabel("Your answer").fill("answer");
      await card.getByRole("button", { name: "Check", exact: true }).click();
      const next = card.getByRole("button", { name: /Next word|Finish session/ });
      const last = /Finish session/.test((await next.textContent()) ?? "");
      await next.click();
      if (last) break;
    }
    await expect(done).toBeVisible();
    await expect(page.getByText(/\d+ of \d+ correct/)).toBeVisible();
  });

  await test.step("take a speaking test and get an evaluation", async () => {
    await page.goto("/speaking");
    await page.getByText("Familiar topics: home, work, studies and interests.").locator("..").getByRole("button", { name: "Start" }).click();
    await expect(page).toHaveURL(/\/speaking\/\d+$/);
    for (const [i, answer] of SPOKEN_ANSWERS.slice(0, 3).entries()) {
      await expect(page.getByText("Examiner", { exact: true })).toBeVisible();
      await typeSpokenAnswer(page, answer, "Send answer");
      // The examiner moves on only after the answer is saved.
      await expect(page.getByText(`${i + 1} answer${i ? "s" : ""} saved.`)).toBeVisible();
    }
    await page.getByRole("button", { name: /Finish early/ }).click();

    await expect(page.getByRole("heading", { name: "Speaking evaluation", exact: true })).toBeVisible({ timeout: 90_000 });
    // Typed answers are labelled as typed and pronunciation is honestly reported as not assessed.
    await expect(page.getByText(/Not assessed: pronunciation can't be judged reliably from a transcript/).first()).toBeVisible();
    await expect(page.getByText(/· typed$/).first()).toBeVisible();
  });

  await test.step("practise reading", async () => {
    await page.goto("/reading");
    await main(page).getByRole("button", { name: "Start", exact: true }).click();
    await expect(page).toHaveURL(/\/reading\/\d+$/);
    await answerAll(main(page).locator("ol > li"), "water");
    await page.getByRole("button", { name: "Submit answers" }).click();
    await expect(page.getByText(/correct at level/)).toBeVisible();
  });

  await test.step("practise listening", async () => {
    await page.goto("/listening");
    await main(page).getByRole("button", { name: "Start", exact: true }).click();
    await expect(page).toHaveURL(/\/listening\/\d+$/);
    await answerAll(main(page).locator("ol > li"), "monday");
    await page.getByRole("button", { name: "Submit answers" }).click();
    await expect(page.getByText("Transcript", { exact: true })).toBeVisible();
  });

  await test.step("earn XP and start a streak", async () => {
    await page.goto("/dashboard");
    await expect(page.getByText("Done for today — nice.")).toBeVisible();
    await expect(page.getByText(/\+[1-9]\d* today/)).toBeVisible();
  });

  await test.step("see progress analytics", async () => {
    await page.goto("/progress");
    await expect(page.getByRole("heading", { name: "Progress", exact: true })).toBeVisible();
    await expect(page.getByText("What changed", { exact: true })).toBeVisible();
    // Every chart has a table view.
    await main(page).getByRole("button", { name: "Table" }).first().click();
    await expect(main(page).getByRole("table").first()).toBeVisible();
  });

  await test.step("switch to the dark theme", async () => {
    const saved = page.waitForResponse((r) => r.url().includes("/api/backend/me") && r.request().method() !== "GET" && r.ok());
    await page.getByRole("radiogroup", { name: "Theme" }).first().getByRole("radio", { name: "Dark" }).click();
    await saved;
    await expect(page.locator("html")).toHaveClass(/\bdark\b/);
  });

  await context.close();

  await test.step("come back later on another device and continue", async () => {
    const later = await browser.newContext({ colorScheme: "light" });
    const again = await later.newPage();
    await again.goto("/login");
    await again.getByLabel("Email").fill(learner.email);
    await again.getByLabel("Password").fill(learner.password);
    await again.getByRole("button", { name: "Sign in" }).click();
    await expect(again).toHaveURL(/\/dashboard$/);
    // The theme follows the account, and the day's progress is still there.
    await expect(again.locator("html")).toHaveClass(/\bdark\b/);
    await expect(again.getByText("Done for today — nice.")).toBeVisible();
    await expect(again.getByText("Take the 15-minute diagnostic")).toHaveCount(0);
    // The evaluated essay is waiting where it was left.
    await again.goto(new URL(submissionUrl).pathname);
    await expect(again.getByRole("heading", { name: "Writing evaluation", exact: true })).toBeVisible();
    await later.close();
  });
});
