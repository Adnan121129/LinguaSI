// Mirrors web/src/lib/types.ts: both clients consume the same LinguaSI API (see /docs on the backend).
// Types for the LinguaSI REST API (see the backend OpenAPI docs at /docs).

export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

export type Profile = {
  goal: "ielts" | "general";
  ielts_module: "academic" | "general_training";
  self_reported_level: string;
  target_band: number;
  test_date: string | null;
  daily_minutes: number;
  preferred_mode: "guided" | "balanced" | "exam";
  confidence: number;
  preferred_topics: string[];
  theme: "light" | "dark" | "system";
  timezone: string;
  keep_recordings: boolean;
  onboarding_completed: boolean;
  diagnostic_completed: boolean;
  estimated_cefr: string | null;
  estimated_band: number | null;
  band_confidence: number;
};

export type User = {
  id: number;
  email: string;
  name: string;
  role: "learner" | "admin";
  is_demo: boolean;
  created_at: string;
  profile: Profile;
};

export type AchievementUnlocked = { code: string; name: string; description: string; icon: string; tier: string; xp_reward: number };

export type ActivityOutcome = {
  xp_gained: number;
  xp_breakdown: { amount: number; reason: string; description: string }[];
  total_xp: number;
  level: number;
  level_title: string;
  leveled_up: boolean;
  streak: number;
  streak_extended: boolean;
  achievements: AchievementUnlocked[];
  mission_progress: string[];
  mission_completed: boolean;
  si_actions: string[];
};

export type Streak = { current: number; longest: number; freezes: number; active_today: boolean; at_risk: boolean };
export type LevelInfo = { level: number; title: string; xp: number; level_floor: number; next_level_xp: number; progress: number };

export type Recommendation = {
  id: number;
  rule: string;
  kind: string;
  title: string;
  description: string;
  why: string;
  priority: number;
  signals: Record<string, unknown>;
  route: string | null;
  focus: string | null;
  estimated_minutes: number;
  source: string;
  created_at: string;
};

export type MissionTask = {
  id: string;
  title: string;
  why: string;
  route: string;
  metric: string;
  target: number;
  progress: number;
  completed: boolean;
  minutes: number;
  xp: number;
  focus: string | null;
};

export type Mission = {
  id: number;
  day: string;
  title: string;
  summary: string;
  focus: string;
  tasks: MissionTask[];
  status: string;
  completed_tasks: number;
  total_tasks: number;
  bonus_xp: number;
  generated_by: string;
};

export type SkillRow = {
  skill: string;
  label: string;
  score: number | null;
  band: number | null;
  trend: string;
  difficulty: number;
  attempts: number;
  confidence: number;
  last_practiced_at: string | null;
};

export type AreaNote = { key: string; label: string; skill: string; score: number | null; reason: string };

export type SIEvent = { id: number; source: string; signal: string; title: string; detail: string; actions: string[]; created_at: string };

export type Mistake = {
  id: number;
  source: string;
  category: string;
  category_label: string;
  subcategory: string;
  label: string;
  original: string;
  corrected: string;
  explanation: string;
  context: string | null;
  severity: "low" | "medium" | "high";
  occurrences: number;
  repeated: boolean;
  status: "unresolved" | "corrected" | "mastered";
  practice_attempts: number;
  practice_correct: number;
  revisit_at: string | null;
  mastered_at: string | null;
  first_seen_at: string;
  last_seen_at: string;
};

export type MistakeDetail = Mistake & { guide: { rule?: string; tip?: string; examples?: string[]; title?: string } | null; related: Mistake[] };

export type VocabCounts = { new: number; learning: number; familiar: number; strong: number; mastered: number; total: number; known: number };

export type Dashboard = {
  greeting: string;
  name: string;
  goal: string;
  goal_label: string;
  module: string;
  estimated_band: number | null;
  band_label: string;
  target_band: number;
  band_confidence: number;
  cefr: string | null;
  days_to_test: number | null;
  level: LevelInfo;
  today_xp: number;
  streak: Streak;
  weekly: { day: string; label: string; minutes: number; xp: number }[];
  weekly_minutes: number;
  weekly_goal_minutes: number;
  skills: SkillRow[];
  vocabulary: VocabCounts & { due: number; strength: number };
  weaknesses: AreaNote[];
  strengths: AreaNote[];
  recent_mistakes: Mistake[];
  recommendation: Recommendation | null;
  recommendations: Recommendation[];
  mission: Mission | null;
  insight: { headline: string; weakness: string | null; weakness_reason: string | null; suggestion: string | null } | null;
  si_feed: SIEvent[];
  onboarding_completed: boolean;
  diagnostic_completed: boolean;
  ai: { provider: string; mock_mode: boolean };
};

export type Progress = {
  chart_questions: Record<string, string>;
  target_band: number;
  estimated_band: number | null;
  cefr: string | null;
  skills: SkillRow[];
  skills_radar: { skill: string; label: string; score: number; target: number }[];
  band_history: ({ day: string; overall: number | null } & Record<string, number | string | null>)[];
  weekly_scores: ({ week: string } & Record<string, number | string | null>)[];
  vocabulary_growth: { day: string; known: number; mastered: number }[];
  mistake_reduction: { week: string; errors: number; words: number; per_100_words: number | null }[];
  consistency: { day: string; minutes: number; xp: number }[];
  totals: { sessions: number; minutes: number; active_days: number; xp: number };
  insights: {
    headline: string;
    improvements: string[];
    regressions: string[];
    recurring_weaknesses: string[];
    skill_gaps: string[];
    next_focus: string;
    provider?: string;
  };
};

export type MissionsResponse = {
  today: Mission | null;
  challenges: { id: number; code: string; title: string; description: string; target: number; progress: number; xp_reward: number; completed: boolean; week: string }[];
  streak: Streak;
  history: { day: string; status: string; completed_tasks: number; total_tasks: number }[];
};

export type AchievementRow = {
  code: string;
  name: string;
  description: string;
  icon: string;
  category: string;
  tier: string;
  xp_reward: number;
  earned: boolean;
  earned_at: string | null;
  progress: number;
  current: number;
  target: number;
};

export type AchievementsResponse = {
  level: LevelInfo;
  streak: Streak;
  achievements: AchievementRow[];
  recent_xp: { amount: number; reason: string; description: string; created_at: string }[];
  completed_challenges: { title: string; week: string; xp_reward: number }[];
};

// --- Writing -----------------------------------------------------------------------------------

export type ChartVisual = {
  chart_type: "line" | "bar" | "pie" | "table" | "process" | string;
  title: string;
  unit?: string;
  x_label?: string;
  y_label?: string;
  categories?: string[];
  series?: { name: string; values: number[] }[];
  steps?: string[];
  rows?: (string | number)[][];
  columns?: string[];
  [key: string]: unknown;
};

export type WritingTask = {
  id: number;
  task_type: "task1" | "task2" | "general";
  module: "academic" | "general_training" | "general_english";
  category: string;
  topic: string;
  title: string;
  prompt: string;
  instructions: string;
  visual: ChartVisual | null;
  min_words: number;
  time_limit_minutes: number;
  difficulty: number;
  source: string;
};

export type WritingErrorItem = {
  id: number;
  category: string;
  subcategory: string;
  original: string;
  corrected: string;
  explanation: string;
  severity: "low" | "medium" | "high";
  start_offset: number | null;
  end_offset: number | null;
  repeated: boolean;
  mistake_id: number | null;
  source: string;
};

export type WritingEvaluation = {
  id: number;
  label: string;
  overall_band: number;
  criteria: { key: string; label: string; band: number; comment: string }[];
  strengths: string[];
  weaknesses: string[];
  task_response_issues: string[];
  cohesion_issues: string[];
  vocabulary_issues: string[];
  advice: string[];
  summary: string;
  recommended_exercise: { focus?: string; title?: string; description?: string };
  metrics: Record<string, unknown>;
  errors: WritingErrorItem[];
  provider: string;
  model: string;
  is_mock: boolean;
  created_at: string;
  disclaimer: string;
};

export type Submission = {
  id: number;
  task: WritingTask;
  mode: "tutor" | "exam";
  content: string;
  word_count: number;
  time_spent_seconds: number;
  status: "draft" | "submitted" | "evaluated" | "evaluation_failed";
  hints_used: number;
  tutor_notes: { question?: string; hints?: string[]; at?: string }[];
  failure_reason: string | null;
  autosaved_at: string | null;
  submitted_at: string | null;
  evaluated_at: string | null;
  created_at: string;
  key_points: string[] | null;
  evaluation: WritingEvaluation | null;
  previous: { submission_id: number; overall_band: number; criteria: Record<string, number>; evaluated_at: string | null; same_task: boolean } | null;
};

export type SubmissionSummary = {
  id: number;
  task_id: number;
  task_title: string;
  task_type: string;
  module: string;
  category: string;
  mode: string;
  status: string;
  word_count: number;
  overall_band: number | null;
  created_at: string;
  evaluated_at: string | null;
};

export type Hint = {
  observations: string[];
  hints: string[];
  guiding_questions: string[];
  structure_feedback: string;
  vocabulary_direction: string[];
  grammar_notes: string[];
  encouragement: string;
  hints_used: number;
};

// --- Vocabulary --------------------------------------------------------------------------------

export type VocabItem = {
  id: number;
  word: string;
  part_of_speech: string;
  definition: string;
  example: string;
  extra_examples: string[];
  synonyms: string[];
  antonyms: string[];
  collocations: string[];
  word_family: Record<string, string>;
  topics: string[];
  cefr: string;
  is_academic: boolean;
  is_phrase: boolean;
};

export type VocabExercise = {
  id: string;
  user_vocab_id: number;
  item_id: number;
  word: string | null;
  state: string;
  type: string;
  prompt: string;
  options: string[] | null;
  hint: string | null;
  input: "choice" | "text" | "sentence";
  reason: string | null;
  reason_detail: string | null;
  is_new: boolean;
};

export type VocabToday = {
  exercises: VocabExercise[];
  due_count: number;
  new_count: number;
  counts: VocabCounts;
  retention: { reviews: number; accuracy: number | null };
  started_at: string;
};

export type ReviewResult = {
  correct: boolean;
  correct_answer: string;
  feedback: string | null;
  state_before: string;
  state_after: string;
  next_review_at: string;
  item: VocabItem;
  xp_gained: number;
  mission_progress: string[];
};

export type UserWord = {
  user_vocab_id: number;
  item: VocabItem;
  state: string;
  correct_count: number;
  incorrect_count: number;
  due_at: string;
  last_reviewed_at: string | null;
  used_in_writing: number;
  used_in_speaking: number;
  reason: string;
  reason_detail: string | null;
  classification: string;
};

export type VocabInsights = {
  counts: VocabCounts;
  due: number;
  retention: { reviews: number; accuracy: number | null };
  groups: Record<string, string[]>;
  group_counts: Record<string, number>;
  relevant_to_weak_areas: string[];
  used_in_writing: string[];
  used_in_speaking: string[];
  growth: { day: string; known: number; mastered: number }[];
};

// --- Practice ----------------------------------------------------------------------------------

export type PracticeItem = { id: string; qtype: string; prompt: string; options: string[] | null; source: string; mistake_id: number | null };

export type PracticeSet = {
  id: number;
  kind: string;
  title: string;
  description: string;
  why: string;
  focus: string | null;
  status: "active" | "completed";
  items: PracticeItem[];
  total: number;
  score: number;
  accuracy: number | null;
  estimated_minutes: number;
  results: { id: string; correct: boolean; your_answer: string; answer: string; explanation: string }[];
  created_at: string;
  completed_at: string | null;
};

export type PracticeSubmitResponse = { practice: PracticeSet; mastered_mistakes: number[]; outcome: ActivityOutcome };

export type MistakeSummary = {
  totals: { unresolved: number; corrected: number; mastered: number; total: number; occurrences: number };
  most_common: Record<string, { subcategory: string; label: string; count: number } | null>;
  recurring: { subcategory: string; category: string; label: string; count: number; last_seen: string; example: { original: string; corrected: string } | null }[];
  by_category: { category: string; label: string; count: number }[];
  weekly_trend: { week: string; count: number }[];
  heatmap: { weeks: string[]; rows: { category: string; label: string; values: number[] }[] };
  due_for_revision: number;
};

// --- Reading & listening -----------------------------------------------------------------------

export type Question = { id: number; position: number; qtype: string; prompt: string; options: string[] | null; word_limit: number | null };

export type QuestionResult = {
  question_id: number;
  qtype: string;
  correct: boolean;
  your_answer: string;
  answer: string;
  explanation: string;
  evidence: string;
  evidence_paragraph?: string | null;
  note?: string | null;
};

export type ReadingAttempt = {
  id: number;
  status: "in_progress" | "submitted";
  passage: { id: number; title: string; topic: string; module: string; difficulty: number; paragraphs: { label: string; text: string }[]; headings: string[]; word_count: number; source: string };
  questions: Question[];
  time_limit_minutes: number;
  difficulty: number;
  started_at: string;
  submitted_at: string | null;
  correct: number;
  total: number;
  accuracy: number | null;
  band: number | null;
  results: QuestionResult[];
  answers: Record<string, string>;
  notice: string | null;
  spotlight: string[];
};

export type ListeningAttempt = {
  id: number;
  status: "in_progress" | "submitted";
  script: {
    id: number;
    title: string;
    topic: string;
    scenario: string;
    difficulty: number;
    context: string;
    speakers: { id: string; name: string; role: string; accent?: string; gender?: string; voice?: string }[];
    segments: { index: number; speaker: string; text: string | null; audio_url: string | null }[];
    speech_rate: number;
    accent: string;
    audio_mode: "server" | "device";
    transcript_hidden: boolean;
    source: string;
  };
  questions: Question[];
  time_limit_minutes: number;
  difficulty: number;
  started_at: string;
  submitted_at: string | null;
  correct: number;
  total: number;
  accuracy: number | null;
  band: number | null;
  replays: number;
  results: QuestionResult[];
  answers: Record<string, string>;
  notice: string | null;
};

export type AttemptSummary = {
  id: number;
  title: string;
  topic: string;
  difficulty: number;
  status: string;
  correct: number;
  total: number;
  accuracy: number | null;
  band: number | null;
  started_at: string;
  submitted_at: string | null;
};

// --- Speaking ----------------------------------------------------------------------------------

export type CueCard = { title: string; prompt: string; bullets: string[]; rounding_off: string };

export type Turn = {
  part: number;
  kind: "question" | "followup" | "cue_card" | "rounding_off";
  question: string;
  examiner_text: string;
  is_followup: boolean;
  cue_card: CueCard | null;
  prep_seconds: number;
  max_seconds: number;
  index: number;
  total: number;
};

export type Transcript = {
  id: number;
  part: number;
  turn_index: number;
  question: string;
  is_followup: boolean;
  transcript: string;
  transcript_source: string;
  duration_seconds: number;
  word_count: number;
  stt_confidence: number | null;
  has_audio: boolean;
  audio_url: string | null;
  metrics: Record<string, unknown>;
  created_at: string;
};

export type SpeakingEvaluation = {
  id: number;
  label: string;
  overall_band: number;
  fluency_coherence: number;
  lexical_resource: number;
  grammatical_range_accuracy: number;
  pronunciation: number | null;
  pronunciation_note: string;
  criteria_feedback: Record<string, { band: number | null; label: string; comment: string }>;
  metrics: Record<string, unknown>;
  hesitation: { level: string; measured: boolean; pauses: number; long_pauses: number; pauses_per_minute: number; fillers_per_minute: number; note: string };
  repeated_words: { word: string; count: number }[];
  fillers: { counts: Record<string, number>; per_minute: number; note: string };
  grammar_patterns: string[];
  errors: { original: string; corrected: string; explanation: string; subcategory?: string; category?: string }[];
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
  expressions_used: string[];
  summary: string;
  provider: string;
  model: string;
  is_mock: boolean;
  created_at: string;
  disclaimer: string;
};

export type SpeakingSession = {
  id: number;
  mode: "full" | "part1" | "part2" | "part3";
  status: "in_progress" | "completed" | "abandoned" | "evaluation_failed";
  topic: string;
  current_part: number;
  current_index: number;
  total_turns: number;
  target_expressions: string[];
  started_at: string | null;
  finished_at: string | null;
  total_speaking_seconds: number;
  failure_reason: string | null;
  current_turn: Turn | null;
  transcripts: Transcript[];
  evaluation: SpeakingEvaluation | null;
};

export type SpeakingSummary = {
  id: number;
  mode: string;
  status: string;
  topic: string;
  overall_band: number | null;
  responses: number;
  total_speaking_seconds: number;
  created_at: string;
  finished_at: string | null;
};

// --- Diagnostic --------------------------------------------------------------------------------

export type DiagnosticItem = { id: string; level?: string | null; qtype?: string | null; prompt: string; options?: string[] | null };

export type DiagnosticStart = {
  attempt_id: number;
  vocabulary: DiagnosticItem[];
  grammar: DiagnosticItem[];
  reading: { title: string; text: string; questions: DiagnosticItem[] };
  listening: { title: string; speakers: { id: string; name: string; role: string; gender?: string; accent?: string }[]; segments: { speaker: string; text: string }[]; questions: DiagnosticItem[] };
  writing: { prompt: string; min_words: number; time_limit_minutes: number };
  speaking: { id: string; prompt: string }[];
  started_at: string;
};

export type DiagnosticResult = {
  attempt_id: number;
  label: string;
  estimated_cefr: string | null;
  estimated_band: number | null;
  confidence: string;
  sections: { key: string; label: string; score: number | null; band: number | null; correct?: number | null; total?: number | null; note?: string | null }[];
  strengths: string[];
  focus_areas: string[];
  writing_feedback: { band: number | null; summary: string; submission_id?: number; top_errors: { original: string; corrected: string; explanation?: string }[] } | null;
  next_steps: { title: string; why: string; route: string }[];
  disclaimer: string;
  completed_at: string | null;
  outcome: ActivityOutcome | null;
};

// --- Tutor & Lab -------------------------------------------------------------------------------

export type TutorMessage = { id: number; role: "user" | "assistant"; content: string; meta: Record<string, unknown>; created_at: string };

export type ScenarioInfo = { id: string; title: string; level: string; ai_role: string; goal: string; phrases: string[] };

export type Conversation = {
  id: number;
  title: string;
  mode: "tutor" | "conversation";
  scenario: string | null;
  scenario_info?: ScenarioInfo | null;
  created_at: string;
  updated_at: string;
  messages?: TutorMessage[];
};

export type LabOverview = {
  goal: string;
  sections: { key: string; title: string; description: string; route: string; count: number | null }[];
  daily_phrase: { phrase: string; meaning: string; example: string; day: string };
};

export type PronunciationResult = {
  match: number;
  matched_words: number;
  total_words: number;
  missing_words: string[];
  unexpected_words: string[];
  tip: string;
  note: string;
  outcome: ActivityOutcome;
};
