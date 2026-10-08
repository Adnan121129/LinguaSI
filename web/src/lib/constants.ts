export const TOPICS = ["technology", "education", "environment", "health", "work", "travel", "culture", "science", "society", "economy", "urban", "media"];

export const LEVELS = [
  { value: "beginner", label: "Beginner", hint: "I know basic words and phrases." },
  { value: "elementary", label: "Elementary", hint: "I can handle simple everyday situations." },
  { value: "intermediate", label: "Intermediate", hint: "I can discuss familiar topics but make mistakes." },
  { value: "upper_intermediate", label: "Upper-intermediate", hint: "I communicate well, with occasional errors." },
  { value: "advanced", label: "Advanced", hint: "I'm fluent and want to polish accuracy and range." },
] as const;

export const BANDS = [4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0];

export const QTYPE_LABELS: Record<string, string> = {
  multiple_choice: "Multiple choice",
  true_false_not_given: "True / False / Not Given",
  yes_no_not_given: "Yes / No / Not Given",
  matching_headings: "Matching headings",
  matching_information: "Matching information",
  sentence_completion: "Sentence completion",
  summary_completion: "Summary completion",
  note_completion: "Note completion",
  form_completion: "Form completion",
  table_completion: "Table completion",
  short_answer: "Short answer",
  gap_fill: "Gap fill",
  error_correction: "Error correction",
  sentence_order: "Sentence order",
  transformation: "Sentence transformation",
};

export const SKILL_LABELS: Record<string, string> = {
  reading: "Reading",
  listening: "Listening",
  writing: "Writing",
  speaking: "Speaking",
  vocabulary: "Vocabulary",
  grammar: "Grammar",
};
