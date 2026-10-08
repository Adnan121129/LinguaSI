"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Clock, FileText, Sparkles, Wand2 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { BandValue } from "@/components/band";
import { useToast } from "@/components/providers/toast";
import { Badge, Button, Card, CardBody, CardHeader, EmptyState, ErrorState, Field, Input, Notice, PageHeader, Select, Skeleton, Tabs } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { Page, Submission, SubmissionSummary, WritingTask } from "@/lib/types";
import { formatDate, taskTypeLabel, titleCase } from "@/lib/utils";

type Mode = "tutor" | "exam";

function TaskCard({ task, mode, onStart, starting }: { task: WritingTask; mode: Mode; onStart: (task: WritingTask) => void; starting: boolean }) {
  return (
    <Card className="flex flex-col">
      <CardBody className="flex flex-1 flex-col gap-3">
        <div className="flex flex-wrap gap-1.5">
          <Badge tone="primary">{taskTypeLabel(task.task_type)}</Badge>
          <Badge>{titleCase(task.category)}</Badge>
          {task.source !== "seed" && <Badge tone="accent">New for you</Badge>}
        </div>
        <h3 className="font-semibold">{task.title}</h3>
        <p className="line-clamp-3 text-sm text-muted-foreground">{task.prompt}</p>
        <div className="mt-auto flex items-center justify-between gap-2 pt-2">
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <Clock className="size-3.5" aria-hidden /> {task.time_limit_minutes} min · {task.min_words}+ words
          </span>
          <Button size="sm" onClick={() => onStart(task)} loading={starting}>
            Start in {mode} mode
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

function WritingHub() {
  const params = useSearchParams();
  const router = useRouter();
  const { push } = useToast();
  const [tab, setTab] = useState<"tasks" | "generate" | "history">("tasks");
  const [mode, setMode] = useState<Mode>(params.get("mode") === "exam" ? "exam" : "tutor");
  const [module, setModule] = useState(params.get("module") ?? "");
  const [taskType, setTaskType] = useState("");
  const [genForm, setGenForm] = useState({ module: params.get("module") ?? "academic", task_type: "task2", topic: "" });
  const [startingId, setStartingId] = useState<number | null>(null);

  const tasks = useQuery({
    queryKey: ["writing-tasks", module, taskType],
    queryFn: () => api<Page<WritingTask>>(`/writing/tasks?page_size=60${module ? `&module=${module}` : ""}${taskType ? `&task_type=${taskType}` : ""}`),
  });
  const history = useQuery({ queryKey: ["writing-history"], queryFn: () => api<Page<SubmissionSummary>>("/writing/history?page_size=50"), enabled: tab === "history" });

  const start = async (task: WritingTask) => {
    setStartingId(task.id);
    try {
      const sub = await api<Submission>("/writing/submissions", { json: { task_id: task.id, mode } });
      router.push(`/writing/${sub.id}`);
    } catch (err) {
      push({ tone: "error", title: "Couldn't start this task", description: errorMessage(err) });
      setStartingId(null);
    }
  };

  const generate = useMutation({
    mutationFn: () =>
      api<{ task: WritingTask; notice: string | null }>("/writing/generate", {
        json: { module: genForm.module, task_type: genForm.module === "general_english" ? "general" : genForm.task_type, topic: genForm.topic || null },
      }),
    onError: (err) => push({ tone: "error", title: "Couldn't generate a task", description: errorMessage(err) }),
  });

  return (
    <div>
      <PageHeader
        title="Writing"
        description="Practise IELTS-style Task 1 and Task 2 or general English writing. Tutor mode gives hints while you write; exam mode is timed with feedback at the end."
        action={
          <Tabs
            value={mode}
            onChange={setMode}
            items={[
              { value: "tutor", label: "Tutor mode" },
              { value: "exam", label: "Exam mode" },
            ]}
          />
        }
      />
      <div className="mb-5">
        <Tabs
          value={tab}
          onChange={setTab}
          items={[
            { value: "tasks", label: "Tasks" },
            { value: "generate", label: "Generate a new task" },
            { value: "history", label: "My submissions" },
          ]}
        />
      </div>

      {tab === "tasks" && (
        <>
          <div className="mb-4 flex flex-wrap gap-3">
            <Select aria-label="Module" value={module} onChange={(e) => setModule(e.target.value)} className="w-auto">
              <option value="">All modules</option>
              <option value="academic">IELTS Academic</option>
              <option value="general_training">IELTS General Training</option>
              <option value="general_english">General English</option>
            </Select>
            <Select aria-label="Task type" value={taskType} onChange={(e) => setTaskType(e.target.value)} className="w-auto">
              <option value="">All task types</option>
              <option value="task1">Task 1</option>
              <option value="task2">Task 2</option>
              <option value="general">General writing</option>
            </Select>
          </div>
          {tasks.isLoading ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-48" />
              ))}
            </div>
          ) : tasks.error ? (
            <ErrorState error={tasks.error} onRetry={() => tasks.refetch()} />
          ) : tasks.data?.items.length ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {tasks.data.items
                .filter((t) => !t.title.startsWith("Diagnostic"))
                .map((task) => (
                  <TaskCard key={task.id} task={task} mode={mode} onStart={start} starting={startingId === task.id} />
                ))}
            </div>
          ) : (
            <EmptyState title="No tasks match these filters" />
          )}
        </>
      )}

      {tab === "generate" && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader icon={<Wand2 className="size-4" />} title="Generate an original task" description="SI writes a new prompt at your level. Tasks are original - never copied from real exams." />
            <CardBody className="space-y-4">
              <Field label="Module" htmlFor="gen-module">
                <Select id="gen-module" value={genForm.module} onChange={(e) => setGenForm((f) => ({ ...f, module: e.target.value }))}>
                  <option value="academic">IELTS Academic</option>
                  <option value="general_training">IELTS General Training</option>
                  <option value="general_english">General English</option>
                </Select>
              </Field>
              {genForm.module !== "general_english" && (
                <Field label="Task" htmlFor="gen-type">
                  <Select id="gen-type" value={genForm.task_type} onChange={(e) => setGenForm((f) => ({ ...f, task_type: e.target.value }))}>
                    <option value="task1">Task 1 ({genForm.module === "academic" ? "chart / process" : "letter"})</option>
                    <option value="task2">Task 2 (essay)</option>
                  </Select>
                </Field>
              )}
              <Field label="Topic (optional)" htmlFor="gen-topic" hint="For example: technology, cities, health">
                <Input id="gen-topic" value={genForm.topic} onChange={(e) => setGenForm((f) => ({ ...f, topic: e.target.value }))} maxLength={60} />
              </Field>
              <Button onClick={() => generate.mutate()} loading={generate.isPending}>
                <Sparkles className="size-4" /> Generate task
              </Button>
            </CardBody>
          </Card>
          <div className="space-y-3">
            {generate.data?.notice && <Notice tone="warning">{generate.data.notice}</Notice>}
            {generate.data ? (
              <TaskCard task={generate.data.task} mode={mode} onStart={start} starting={startingId === generate.data.task.id} />
            ) : (
              <EmptyState icon={<FileText className="size-5" />} title="Your generated task appears here" description="Choose the module and task type, then generate." />
            )}
          </div>
        </div>
      )}

      {tab === "history" &&
        (history.isLoading ? (
          <Skeleton className="h-64" />
        ) : history.error ? (
          <ErrorState error={history.error} onRetry={() => history.refetch()} />
        ) : history.data?.items.length ? (
          <Card>
            <ul className="divide-y divide-border">
              {history.data.items.map((s) => (
                <li key={s.id}>
                  <Link href={`/writing/${s.id}`} className="flex flex-wrap items-center gap-4 px-5 py-4 hover:bg-muted/50">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">{s.task_title}</p>
                      <p className="text-sm text-muted-foreground">
                        {taskTypeLabel(s.task_type)} · {s.word_count} words · {formatDate(s.evaluated_at ?? s.created_at)}
                      </p>
                    </div>
                    {s.overall_band !== null ? (
                      <BandValue band={s.overall_band} size="sm" label={null} />
                    ) : (
                      <Badge tone={s.status === "evaluation_failed" ? "warning" : "default"}>{s.status === "draft" ? "Draft" : s.status === "evaluation_failed" ? "Needs analysis" : titleCase(s.status)}</Badge>
                    )}
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        ) : (
          <EmptyState title="No submissions yet" description="Start a task to see your history and band trend here." />
        ))}
    </div>
  );
}

export default function WritingPage() {
  return (
    <Suspense>
      <WritingHub />
    </Suspense>
  );
}
