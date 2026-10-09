import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { QuestionForm, withEvidence } from "@/components/comprehension/question-form";
import type { Question, QuestionResult } from "@/lib/types";

const QUESTIONS: Question[] = [
  { id: 1, position: 1, qtype: "true_false_not_given", prompt: "Urban gardens reduce summer temperatures.", options: null, word_limit: null },
  { id: 2, position: 2, qtype: "sentence_completion", prompt: "Most volunteers join through ______.", options: null, word_limit: 2 },
  { id: 3, position: 3, qtype: "matching_headings", prompt: "Paragraph B", options: null, word_limit: null },
];
const HEADINGS = ["i. Costs", "ii. Volunteers", "iii. Climate", "iv. History", "v. Design", "vi. Funding", "vii. Results"];

describe("QuestionForm", () => {
  it("offers the right input for each IELTS question type", () => {
    const onChange = vi.fn();
    render(<QuestionForm questions={QUESTIONS} answers={{}} onChange={onChange} headings={HEADINGS} />);

    expect(screen.getAllByRole("radio").map((r) => r.getAttribute("value"))).toEqual(["TRUE", "FALSE", "NOT GIVEN"]);
    fireEvent.click(screen.getByRole("radio", { name: "NOT GIVEN" }));
    expect(onChange).toHaveBeenCalledWith(1, "NOT GIVEN");

    expect(screen.getByText("No more than 2 words")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "Answer for question 2" }), { target: { value: "local schools" } });
    expect(onChange).toHaveBeenCalledWith(2, "local schools");

    // Long option lists (seven headings) use a compact select.
    fireEvent.change(screen.getByRole("combobox", { name: "Answer for question 3" }), { target: { value: "ii. Volunteers" } });
    expect(onChange).toHaveBeenCalledWith(3, "ii. Volunteers");
  });

  it("marks answers after submission and links each one to its evidence", () => {
    const results: QuestionResult[] = [
      { question_id: 1, qtype: "true_false_not_given", correct: false, your_answer: "TRUE", answer: "NOT GIVEN", explanation: "Temperatures are never measured in the passage.", evidence: "Residents say the gardens feel cooler...", evidence_paragraph: "C", note: null },
      { question_id: 2, qtype: "sentence_completion", correct: true, your_answer: "local schools", answer: "local schools", explanation: "", evidence: null, evidence_paragraph: null, note: null },
    ] as QuestionResult[];
    const onShowEvidence = vi.fn();
    render(<QuestionForm questions={QUESTIONS.slice(0, 2)} answers={{}} onChange={vi.fn()} results={results} onShowEvidence={onShowEvidence} />);

    expect(screen.getByLabelText("Incorrect")).toBeInTheDocument();
    expect(screen.getByLabelText("Correct")).toBeInTheDocument();
    expect(screen.getByText("TRUE")).toBeInTheDocument();
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Residents say the gardens feel cooler/ }));
    expect(onShowEvidence).toHaveBeenCalledWith(results[0]);
    expect(screen.getByText(/\(paragraph C\)/)).toBeInTheDocument();
  });
});

describe("withEvidence", () => {
  const PASSAGE = "Residents say the gardens feel cooler in July. Councils have not measured this.";

  it("highlights the quoted evidence, ignoring case and a trailing ellipsis", () => {
    render(<p>{withEvidence(PASSAGE, "residents say the gardens feel cooler...")}</p>);
    const mark = document.querySelector("mark");
    expect(mark).toHaveTextContent(/^Residents say the gardens feel cooler$/);
  });

  it("leaves the text alone when the quote is missing or not found", () => {
    expect(withEvidence(PASSAGE, null)).toBe(PASSAGE);
    expect(withEvidence(PASSAGE, "a sentence that is not there")).toBe(PASSAGE);
  });
});
