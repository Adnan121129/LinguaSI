"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Hourglass, Square, Volume2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { SIActions, useToast } from "@/components/providers/toast";
import { SpeakingEvaluationView } from "@/components/speaking/evaluation-view";
import { AnswerRecorder } from "@/components/speech/answer-recorder";
import type { Recording } from "@/components/speech/use-recorder";
import { Badge, Button, Card, CardBody, ErrorState, Notice, PageSkeleton, ProgressBar } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { loadVoices, speak, stopSpeaking, ttsSupported } from "@/lib/speech";
import type { ActivityOutcome, SpeakingSession, Transcript, Turn } from "@/lib/types";
import { formatDuration } from "@/lib/utils";

function useExaminerVoice() {
  const voice = useRef<SpeechSynthesisVoice | undefined>(undefined);
  useEffect(() => {
    loadVoices().then((voices) => {
      voice.current = voices.find((v) => v.lang === "en-GB") ?? voices.find((v) => v.lang.startsWith("en"));
    });
    return () => stopSpeaking();
  }, []);
  return useCallback((text: string) => (ttsSupported() ? speak(text, { voice: voice.current, rate: 0.95 }) : Promise.resolve()), []);
}

function PrepTimer({ seconds, onDone }: { seconds: number; onDone: () => void }) {
  const [left, setLeft] = useState(seconds);
  useEffect(() => {
    if (left <= 0) {
      onDone();
      return;
    }
    const id = window.setTimeout(() => setLeft((l) => l - 1), 1000);
    return () => window.clearTimeout(id);
  }, [left, onDone]);
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-2xl bg-warning-soft p-4">
      <Hourglass className="size-5 text-warning" aria-hidden />
      <p className="flex-1 text-sm">
        Preparation time: <span className="font-mono font-semibold tabular-nums">{formatDuration(left)}</span>. Make short notes, then speak for up to two minutes.
      </p>
      <Button size="sm" variant="outline" onClick={onDone}>
        I&apos;m ready
      </Button>
    </div>
  );
}

function TestRunner({ session, onFinished }: { session: SpeakingSession; onFinished: (outcome: ActivityOutcome) => void }) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const { push, celebrate } = useToast();
  const say = useExaminerVoice();
  const [turn, setTurn] = useState<Turn | null>(session.current_turn);
  const [answers, setAnswers] = useState<Transcript[]>(session.transcripts);
  const [preparing, setPreparing] = useState(false);
  const spoken = useRef<string | null>(null);
  const endPreparation = useCallback(() => setPreparing(false), []);

  // The examiner reads each new question aloud; Part 2 starts with a one-minute preparation.
  useEffect(() => {
    if (!turn) return;
    const key = `${turn.index}-${turn.is_followup}-${turn.question}`;
    if (spoken.current === key) return;
    spoken.current = key;
    setPreparing(turn.kind === "cue_card" && turn.prep_seconds > 0);
    void say(turn.examiner_text);
  }, [turn, say]);

  const respond = useMutation({
    mutationFn: async (rec: Recording) => {
      const form = new FormData();
      form.set("session_id", String(session.id));
      form.set("transcript", rec.transcript);
      form.set("transcript_source", rec.transcriptSource === "typed" ? "typed" : "browser");
      if (rec.durationSeconds) form.set("duration_seconds", String(rec.durationSeconds));
      if (rec.pauses) form.set("pauses", JSON.stringify(rec.pauses));
      if (rec.blob) form.set("audio", rec.blob, `answer.${rec.mimeType.includes("mp4") ? "m4a" : rec.mimeType.includes("ogg") ? "ogg" : "webm"}`);
      return api<{ transcript: Transcript; next: Turn | null; done: boolean }>("/speaking/session/respond", { form });
    },
    onSuccess: (res) => {
      setAnswers((a) => [...a, res.transcript]);
      if (res.done) finish.mutate();
      else setTurn(res.next);
    },
    onError: (err) => push({ tone: "error", title: "Your answer wasn't sent", description: errorMessage(err) }),
  });

  const finish = useMutation({
    mutationFn: () => api<{ session: SpeakingSession; outcome: ActivityOutcome }>("/speaking/session/finish", { json: { session_id: session.id } }),
    onSuccess: (res) => {
      stopSpeaking();
      queryClient.setQueryData(["speaking-session", session.id], res.session);
      ["dashboard", "speaking-history", "mistakes"].forEach((k) => queryClient.invalidateQueries({ queryKey: [k] }));
      celebrate(res.outcome);
      onFinished(res.outcome);
    },
    onError: () => queryClient.invalidateQueries({ queryKey: ["speaking-session", session.id] }),
  });

  const abandon = useMutation({
    mutationFn: () => api(`/speaking/session/${session.id}/abandon`, { method: "POST" }),
    onSuccess: () => router.push("/speaking"),
  });

  if (finish.isPending) {
    return (
      <Card>
        <CardBody className="space-y-3 text-center">
          <p className="text-lg font-semibold">The examiner is reviewing your answers…</p>
          <p className="text-sm text-muted-foreground">Analysing fluency, vocabulary, grammar and pronunciation evidence.</p>
          <ProgressBar value={70} className="mx-auto max-w-sm" label="Evaluating" />
        </CardBody>
      </Card>
    );
  }
  if (finish.error) return <ErrorState title="Evaluation didn't finish" error={finish.error} onRetry={() => finish.mutate()} />;
  if (!turn) {
    return (
      <Card>
        <CardBody className="space-y-3">
          <p>All questions are answered.</p>
          <Button onClick={() => finish.mutate()}>Get my evaluation</Button>
        </CardBody>
      </Card>
    );
  }

  const isCueCard = turn.kind === "cue_card";
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Badge tone="primary">Part {turn.part}</Badge>
        <span className="text-sm text-muted-foreground">
          Question {Math.min(turn.index + 1, turn.total)} of {turn.total}
          {turn.is_followup && " · follow-up"}
        </span>
        <ProgressBar className="max-w-xs flex-1" value={(turn.index / turn.total) * 100} label="Test progress" />
      </div>

      <Card>
        <CardBody className="space-y-4">
          <div className="flex items-start gap-3">
            <div className="grid size-10 shrink-0 place-items-center rounded-full bg-primary-soft text-sm font-semibold text-primary">EX</div>
            <div className="flex-1">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Examiner</p>
              <p className="mt-1 text-lg leading-relaxed">{turn.examiner_text}</p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => say(turn.examiner_text)} aria-label="Repeat the question" disabled={!ttsSupported()}>
              <Volume2 className="size-4" />
            </Button>
          </div>
          {isCueCard && turn.cue_card && (
            <div className="rounded-2xl border-2 border-dashed border-primary/40 p-4">
              <p className="font-semibold">{turn.cue_card.title}</p>
              <p className="mt-1 text-sm">{turn.cue_card.prompt}</p>
              <p className="mt-2 text-sm text-muted-foreground">You should say:</p>
              <ul className="mt-1 list-inside list-disc text-sm">{turn.cue_card.bullets.map((b) => <li key={b}>{b}</li>)}</ul>
            </div>
          )}
        </CardBody>
      </Card>

      {session.target_expressions.length > 0 && turn.index === 0 && !turn.is_followup && (
        <Notice tone="primary">Try to use naturally: {session.target_expressions.map((e) => `“${e}”`).join(", ")} — words from your vocabulary list.</Notice>
      )}

      {preparing ? (
        <PrepTimer seconds={turn.prep_seconds} onDone={endPreparation} />
      ) : (
        <AnswerRecorder key={`${turn.index}-${turn.is_followup}`} onAnswer={(rec) => respond.mutateAsync(rec).then(() => undefined)} busy={respond.isPending} maxSeconds={turn.max_seconds} />
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
        <p className="text-xs text-muted-foreground">Like the real test, there are no scores until the end. {answers.length} answer{answers.length === 1 ? "" : "s"} saved.</p>
        <div className="flex gap-2">
          {answers.length > 0 && (
            <Button variant="outline" size="sm" onClick={() => finish.mutate()}>
              <Square className="size-3.5" /> Finish early &amp; evaluate
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={() => abandon.mutate()} loading={abandon.isPending}>
            Quit test
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function SpeakingSessionPage() {
  const { id } = useParams<{ id: string }>();
  const sessionId = Number(id);
  const queryClient = useQueryClient();
  const [outcome, setOutcome] = useState<ActivityOutcome | null>(null);
  const { data, error, isLoading, refetch } = useQuery({ queryKey: ["speaking-session", sessionId], queryFn: () => api<SpeakingSession>(`/speaking/sessions/${sessionId}`), staleTime: Infinity });
  const retry = useMutation({
    mutationFn: () => api<{ session: SpeakingSession; outcome: ActivityOutcome }>("/speaking/session/finish", { json: { session_id: sessionId } }),
    onSuccess: (res) => {
      queryClient.setQueryData(["speaking-session", sessionId], res.session);
      setOutcome(res.outcome);
    },
  });
  if (isLoading) return <PageSkeleton />;
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />;
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <Link href="/speaking" className="text-sm text-muted-foreground hover:text-foreground">
          ← Speaking
        </Link>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">{data.status === "completed" ? "Speaking evaluation" : "Speaking test"}</h1>
        <p className="text-sm text-muted-foreground">Topic: {data.topic}</p>
      </div>
      {data.status === "completed" && data.evaluation ? (
        <>
          <SIActions outcome={outcome} />
          <SpeakingEvaluationView session={data} />
        </>
      ) : data.status === "evaluation_failed" ? (
        <div className="space-y-4">
          <Notice tone="warning">AI speaking analysis was temporarily unavailable. Your answers are saved — you can run the evaluation again.</Notice>
          {retry.error && <ErrorState error={retry.error} />}
          <Button onClick={() => retry.mutate()} loading={retry.isPending}>
            Evaluate my answers
          </Button>
        </div>
      ) : data.status === "abandoned" ? (
        <Notice tone="default">This test was ended without an evaluation.</Notice>
      ) : (
        <TestRunner key={data.id} session={data} onFinished={setOutcome} />
      )}
    </div>
  );
}
