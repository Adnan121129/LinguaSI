import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Stack, useLocalSearchParams } from "expo-router";
import { ChevronDown, ChevronUp, Clock, Lightbulb, RotateCcw, Send } from "lucide-react-native";
import { useEffect, useRef, useState } from "react";
import { KeyboardAvoidingView, Platform, Pressable, TextInput, View } from "react-native";

import { TaskVisual } from "@/components/task-visual";
import { SIActions, useToast } from "@/components/toast";
import { Button, Card, ErrorState, Input, Notice, QueryView, Row, Screen, Text } from "@/components/ui";
import { WritingEvaluation } from "@/components/writing-evaluation";
import { api, errorMessage } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import type { ActivityOutcome, Hint, Submission } from "@/lib/types";
import { formatDuration, taskTypeLabel, titleCase, wordCount } from "@/lib/utils";

function HintList({ title, items, muted }: { title: string; items: string[]; muted?: boolean }) {
  if (!items.length) return null;
  return (
    <View style={{ gap: 4 }}>
      <Text variant="small" weight="600">{title}</Text>
      {items.map((item) => (
        <Text key={item} variant="small" tone={muted ? "muted" : "default"}>
          • {item}
        </Text>
      ))}
    </View>
  );
}

function Editor({ submission, onEvaluated }: { submission: Submission; onEvaluated: (outcome: ActivityOutcome) => void }) {
  const { colors } = useTheme();
  const queryClient = useQueryClient();
  const { push, celebrate } = useToast();
  const task = submission.task;
  const exam = submission.mode === "exam";
  const [content, setContent] = useState(submission.content);
  const [elapsed, setElapsed] = useState(submission.time_spent_seconds);
  const [savedAt, setSavedAt] = useState<string | null>(submission.autosaved_at);
  const [showTask, setShowTask] = useState(true);
  const [question, setQuestion] = useState("");
  const [hints, setHints] = useState<Hint | null>(null);
  const lastSaved = useRef(submission.content);
  const words = wordCount(content);
  const remaining = task.time_limit_minutes * 60 - elapsed;

  useEffect(() => {
    const id = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const save = useMutation({
    mutationFn: (text: string) => api<{ saved_at: string; word_count: number }>(`/writing/submissions/${submission.id}`, { method: "PUT", json: { content: text, time_spent_seconds: elapsed } }),
    onSuccess: (res, text) => {
      lastSaved.current = text;
      setSavedAt(res.saved_at);
    },
  });

  // Autosave a few seconds after the learner stops typing.
  useEffect(() => {
    if (content === lastSaved.current) return;
    const id = setTimeout(() => save.mutate(content), 2500);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [content]);

  const hint = useMutation({
    mutationFn: () => api<Hint>(`/writing/submissions/${submission.id}/hint`, { json: { question: question.trim() || null, content } }),
    onSuccess: (h) => {
      setHints(h);
      setQuestion("");
    },
    onError: (err) => push({ tone: "error", title: "Hints are unavailable right now", description: errorMessage(err) }),
  });

  const evaluate = useMutation({
    mutationFn: () => api<{ submission: Submission; outcome: ActivityOutcome }>("/writing/evaluate", { json: { submission_id: submission.id, content, time_spent_seconds: elapsed } }),
    onSuccess: (res) => {
      onEvaluated(res.outcome);
      celebrate(res.outcome);
      queryClient.setQueryData(["submission", submission.id], res.submission);
      ["writing-history", "dashboard", "mistakes", "mistake-summary"].forEach((key) => queryClient.invalidateQueries({ queryKey: [key] }));
    },
    onError: () => queryClient.invalidateQueries({ queryKey: ["submission", submission.id] }),
  });

  return (
    <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} keyboardVerticalOffset={90} style={{ flex: 1 }}>
      <Screen>
        <Card>
          <Pressable onPress={() => setShowTask((s) => !s)} accessibilityRole="button" accessibilityState={{ expanded: showTask }} style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <View style={{ flex: 1, gap: 2 }}>
              <Text weight="600">{task.title}</Text>
              <Text variant="caption" tone="muted">
                {taskTypeLabel(task.task_type)} · {titleCase(task.module)} · {titleCase(task.category)}
              </Text>
            </View>
            {showTask ? <ChevronUp size={18} color={colors.mutedForeground} /> : <ChevronDown size={18} color={colors.mutedForeground} />}
          </Pressable>
          {showTask ? (
            <>
              <Text variant="small">{task.prompt}</Text>
              {task.instructions ? <Text variant="small" tone="muted">{task.instructions}</Text> : null}
            </>
          ) : null}
        </Card>
        {showTask && task.visual ? <TaskVisual visual={task.visual} /> : null}

        {submission.status === "evaluation_failed" ? <Notice tone="warning">AI analysis was temporarily unavailable last time. Your response is saved — submit again to analyse it.</Notice> : null}
        {evaluate.error ? <ErrorState title="Analysis didn't finish" error={evaluate.error} onRetry={() => evaluate.mutate()} /> : null}

        <Card style={{ padding: 0, gap: 0 }}>
          <Row style={{ justifyContent: "space-between", paddingHorizontal: 14, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border }}>
            <Text variant="small" tone={words >= task.min_words ? "success" : "muted"} weight={words >= task.min_words ? "600" : "400"}>
              {words} / {task.min_words} words
            </Text>
            <Row gap={10}>
              <Row gap={4}>
                <Clock size={13} color={exam && remaining < 0 ? colors.danger : colors.mutedForeground} />
                <Text variant="small" tone={exam && remaining < 0 ? "danger" : "muted"}>
                  {exam ? (remaining >= 0 ? `${formatDuration(remaining)} left` : `${formatDuration(-remaining)} over`) : formatDuration(elapsed)}
                </Text>
              </Row>
              <Text variant="caption" tone={save.isError ? "danger" : "muted"}>{save.isPending ? "Saving…" : save.isError ? "Not saved yet" : savedAt ? "Saved" : ""}</Text>
            </Row>
          </Row>
          <TextInput
            value={content}
            onChangeText={setContent}
            multiline
            placeholder={task.task_type === "task1" ? "Summarise the main features and make comparisons…" : "Plan your position, then write your response here…"}
            placeholderTextColor={colors.mutedForeground}
            accessibilityLabel="Your response"
            autoCorrect={!exam}
            spellCheck={!exam}
            textAlignVertical="top"
            style={{ minHeight: 320, padding: 14, fontSize: 16, lineHeight: 24, color: colors.foreground }}
          />
        </Card>
        <Text variant="caption" tone="muted">{exam ? "Exam mode: no hints, spell-check off, timed like the real test." : "Tutor mode: ask for hints at any time."}</Text>
        <Button
          title={evaluate.isPending ? "Analysing your writing…" : submission.status === "evaluation_failed" ? "Analyse again" : "Submit for evaluation"}
          icon={submission.status === "evaluation_failed" ? RotateCcw : Send}
          size="lg"
          loading={evaluate.isPending}
          disabled={words < 20}
          onPress={() => evaluate.mutate()}
        />

        {!exam ? (
          <Card>
            <Row>
              <Lightbulb size={16} color={colors.primary} />
              <Text variant="subheading">SI Tutor</Text>
            </Row>
            <Text variant="caption" tone="muted">Hints and guiding questions — the tutor never writes your essay for you.</Text>
            <Input value={question} onChangeText={setQuestion} placeholder="Ask about your draft (optional)" accessibilityLabel="Question for the tutor" maxLength={500} />
            <Button title="Get a hint" variant="secondary" loading={hint.isPending} onPress={() => hint.mutate()} />
            {hints ? (
              <View style={{ gap: 10 }}>
                <HintList title="What I notice" items={hints.observations} muted />
                <HintList title="Hints" items={hints.hints} />
                <HintList title="Ask yourself" items={hints.guiding_questions} muted />
                {hints.structure_feedback ? (
                  <View style={{ backgroundColor: colors.muted, borderRadius: 12, padding: 10 }}>
                    <Text variant="small">{hints.structure_feedback}</Text>
                  </View>
                ) : null}
                {hints.vocabulary_direction.length ? <Text variant="small" tone="muted">Useful language: {hints.vocabulary_direction.join(" · ")}</Text> : null}
                {hints.encouragement ? <Text variant="small" tone="primary">{hints.encouragement}</Text> : null}
                <Text variant="caption" tone="muted">Hints used: {hints.hints_used}</Text>
              </View>
            ) : null}
          </Card>
        ) : null}
      </Screen>
    </KeyboardAvoidingView>
  );
}

export default function SubmissionScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const submissionId = Number(id);
  const submission = useQuery({ queryKey: ["submission", submissionId], queryFn: () => api<Submission>(`/writing/submissions/${submissionId}`) });
  const [outcome, setOutcome] = useState<ActivityOutcome | null>(null);
  return (
    <QueryView query={submission}>
      {(data) =>
        data.status === "evaluated" && data.evaluation ? (
          <Screen>
            <Stack.Screen options={{ title: "Writing evaluation" }} />
            <SIActions outcome={outcome} />
            <WritingEvaluation submission={data} />
          </Screen>
        ) : (
          <>
            <Stack.Screen options={{ title: data.task.title }} />
            <Editor key={data.id} submission={data} onEvaluated={setOutcome} />
          </>
        )
      }
    </QueryView>
  );
}
