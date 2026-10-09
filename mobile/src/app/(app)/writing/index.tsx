import { useMutation, useQuery } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { Clock, FileText, Sparkles } from "lucide-react-native";
import { useState } from "react";
import { ActivityIndicator, ScrollView } from "react-native";

import { BandValue } from "@/components/band";
import { useToast } from "@/components/toast";
import { Badge, Button, Card, Chip, EmptyState, ErrorState, Input, ListRow, Notice, Row, Screen, Segmented, Text } from "@/components/ui";
import { useRefetchOnFocus } from "@/hooks/use-refetch-on-focus";
import { api, errorMessage } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import type { Page, Submission, SubmissionSummary, WritingTask } from "@/lib/types";
import { formatDate, taskTypeLabel, titleCase } from "@/lib/utils";

type Mode = "tutor" | "exam";
const MODULES = [
  ["academic", "IELTS Academic"],
  ["general_training", "IELTS General Training"],
  ["general_english", "General English"],
] as const;

function TaskCard({ task, mode, onStart, starting }: { task: WritingTask; mode: Mode; onStart: (task: WritingTask) => void; starting: boolean }) {
  const { colors } = useTheme();
  return (
    <Card>
      <Row wrap gap={6}>
        <Badge tone="primary" label={taskTypeLabel(task.task_type)} />
        <Badge label={titleCase(task.category)} />
        {task.source !== "seed" ? <Badge tone="accent" label="New for you" /> : null}
      </Row>
      <Text weight="600">{task.title}</Text>
      <Text variant="small" tone="muted" numberOfLines={3}>{task.prompt}</Text>
      <Row style={{ justifyContent: "space-between" }}>
        <Row gap={4}>
          <Clock size={13} color={colors.mutedForeground} />
          <Text variant="caption" tone="muted">
            {task.time_limit_minutes} min · {task.min_words}+ words
          </Text>
        </Row>
        <Button title={`Start (${mode})`} size="sm" loading={starting} onPress={() => onStart(task)} />
      </Row>
    </Card>
  );
}

export default function WritingHub() {
  const params = useLocalSearchParams<{ mode?: string; module?: string }>();
  const { push } = useToast();
  const [tab, setTab] = useState<"tasks" | "generate" | "history">("tasks");
  const [mode, setMode] = useState<Mode>(params.mode === "exam" ? "exam" : "tutor");
  const [module, setModule] = useState(params.module ?? "");
  const [taskType, setTaskType] = useState("");
  const [genForm, setGenForm] = useState({ module: params.module ?? "academic", task_type: "task2", topic: "" });
  const [startingId, setStartingId] = useState<number | null>(null);

  const tasks = useQuery({
    queryKey: ["writing-tasks", module, taskType],
    queryFn: () => api<Page<WritingTask>>(`/writing/tasks?page_size=60${module ? `&module=${module}` : ""}${taskType ? `&task_type=${taskType}` : ""}`),
  });
  const history = useQuery({ queryKey: ["writing-history"], queryFn: () => api<Page<SubmissionSummary>>("/writing/history?page_size=50"), enabled: tab === "history" });
  useRefetchOnFocus(history.refetch);

  async function start(task: WritingTask) {
    setStartingId(task.id);
    try {
      const sub = await api<Submission>("/writing/submissions", { json: { task_id: task.id, mode } });
      router.push(`/writing/${sub.id}`);
    } catch (err) {
      push({ tone: "error", title: "Couldn't start this task", description: errorMessage(err) });
    } finally {
      setStartingId(null);
    }
  }

  const generate = useMutation({
    mutationFn: () =>
      api<{ task: WritingTask; notice: string | null }>("/writing/generate", {
        json: { module: genForm.module, task_type: genForm.module === "general_english" ? "general" : genForm.task_type, topic: genForm.topic.trim() || null },
      }),
    onError: (err) => push({ tone: "error", title: "Couldn't generate a task", description: errorMessage(err) }),
  });

  return (
    <Screen refreshing={tasks.isRefetching} onRefresh={tasks.refetch}>
      <Text tone="muted">IELTS-style Task 1 and Task 2 or general English writing. Tutor mode gives hints while you write; exam mode is timed with feedback at the end.</Text>
      <Segmented
        value={mode}
        onChange={setMode}
        options={[
          { value: "tutor", label: "Tutor mode" },
          { value: "exam", label: "Exam mode" },
        ]}
      />
      <Segmented
        value={tab}
        onChange={setTab}
        options={[
          { value: "tasks", label: "Tasks" },
          { value: "generate", label: "New task" },
          { value: "history", label: "My work" },
        ]}
      />

      {tab === "tasks" ? (
        <>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
            <Chip label="All modules" selected={!module} onPress={() => setModule("")} />
            {MODULES.map(([value, label]) => (
              <Chip key={value} label={label} selected={module === value} onPress={() => setModule(value)} />
            ))}
          </ScrollView>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
            <Chip label="All task types" selected={!taskType} onPress={() => setTaskType("")} />
            <Chip label="Task 1" selected={taskType === "task1"} onPress={() => setTaskType("task1")} />
            <Chip label="Task 2" selected={taskType === "task2"} onPress={() => setTaskType("task2")} />
            <Chip label="General writing" selected={taskType === "general"} onPress={() => setTaskType("general")} />
          </ScrollView>
          {tasks.isLoading ? (
            <ActivityIndicator />
          ) : tasks.error ? (
            <ErrorState error={tasks.error} onRetry={() => tasks.refetch()} />
          ) : tasks.data?.items.length ? (
            tasks.data.items.filter((t) => !t.title.startsWith("Diagnostic")).map((task) => <TaskCard key={task.id} task={task} mode={mode} onStart={start} starting={startingId === task.id} />)
          ) : (
            <EmptyState title="No tasks match these filters" />
          )}
        </>
      ) : null}

      {tab === "generate" ? (
        <>
          <Card>
            <Text variant="subheading">Generate an original task</Text>
            <Text variant="small" tone="muted">SI writes a new prompt at your level. Tasks are original — never copied from real exams.</Text>
            <Text variant="small" weight="600">Module</Text>
            <Row wrap>
              {MODULES.map(([value, label]) => (
                <Chip key={value} label={label} selected={genForm.module === value} onPress={() => setGenForm((f) => ({ ...f, module: value }))} />
              ))}
            </Row>
            {genForm.module !== "general_english" ? (
              <>
                <Text variant="small" weight="600">Task</Text>
                <Row wrap>
                  <Chip label={`Task 1 (${genForm.module === "academic" ? "chart / process" : "letter"})`} selected={genForm.task_type === "task1"} onPress={() => setGenForm((f) => ({ ...f, task_type: "task1" }))} />
                  <Chip label="Task 2 (essay)" selected={genForm.task_type === "task2"} onPress={() => setGenForm((f) => ({ ...f, task_type: "task2" }))} />
                </Row>
              </>
            ) : null}
            <Input label="Topic (optional)" value={genForm.topic} onChangeText={(topic) => setGenForm((f) => ({ ...f, topic }))} maxLength={60} hint="For example: technology, cities, health" />
            <Button title="Generate task" icon={Sparkles} loading={generate.isPending} onPress={() => generate.mutate()} />
          </Card>
          {generate.data?.notice ? <Notice tone="warning">{generate.data.notice}</Notice> : null}
          {generate.data ? (
            <TaskCard task={generate.data.task} mode={mode} onStart={start} starting={startingId === generate.data.task.id} />
          ) : (
            <EmptyState icon={FileText} title="Your generated task appears here" description="Choose the module and task type, then generate." />
          )}
        </>
      ) : null}

      {tab === "history" ? (
        history.isLoading ? (
          <ActivityIndicator />
        ) : history.error ? (
          <ErrorState error={history.error} onRetry={() => history.refetch()} />
        ) : history.data?.items.length ? (
          <Card style={{ gap: 0, paddingVertical: 4 }}>
            {history.data.items.map((s) => (
              <ListRow
                key={s.id}
                title={s.task_title}
                subtitle={`${taskTypeLabel(s.task_type)} · ${s.word_count} words · ${formatDate(s.evaluated_at ?? s.created_at)}`}
                right={
                  s.overall_band !== null ? (
                    <BandValue band={s.overall_band} size="sm" label={null} />
                  ) : (
                    <Badge tone={s.status === "evaluation_failed" ? "warning" : "muted"} label={s.status === "draft" ? "Draft" : s.status === "evaluation_failed" ? "Needs analysis" : titleCase(s.status)} />
                  )
                }
                onPress={() => router.push(`/writing/${s.id}`)}
              />
            ))}
          </Card>
        ) : (
          <EmptyState title="No submissions yet" description="Start a task to see your history and band trend here." />
        )
      ) : null}
    </Screen>
  );
}
