"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Info } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { BandValue } from "@/components/band";
import { QuestionForm, withEvidence } from "@/components/comprehension/question-form";
import { SIActions, useToast } from "@/components/providers/toast";
import { ListeningPlayer } from "@/components/speech/listening-player";
import { Button, Card, CardBody, CardHeader, ErrorState, Notice, PageSkeleton } from "@/components/ui";
import { useTimeOnTask } from "@/hooks/use-time-on-task";
import { api, errorMessage, mediaUrl } from "@/lib/api";
import type { ActivityOutcome, ListeningAttempt, QuestionResult } from "@/lib/types";
import { percent, titleCase } from "@/lib/utils";

export default function ListeningAttemptPage() {
  const { id } = useParams<{ id: string }>();
  const attemptId = Number(id);
  const queryClient = useQueryClient();
  const { push, celebrate } = useToast();
  const elapsedSeconds = useTimeOnTask();
  const { data, error, isLoading, refetch } = useQuery({ queryKey: ["listening-attempt", attemptId], queryFn: () => api<ListeningAttempt>(`/listening/attempts/${attemptId}`), staleTime: Infinity });
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [plays, setPlays] = useState(0);
  const [evidence, setEvidence] = useState<QuestionResult | null>(null);
  const [outcome, setOutcome] = useState<ActivityOutcome | null>(null);

  const replay = useMutation({ mutationFn: () => api(`/listening/attempts/${attemptId}/replay`, { method: "POST" }) });
  const submit = useMutation({
    mutationFn: () =>
      api<{ attempt: ListeningAttempt; outcome: ActivityOutcome }>("/listening/submit", {
        json: { attempt_id: attemptId, answers, time_spent_seconds: Math.min(elapsedSeconds(), 14400), replays: Math.max(0, plays - 1) },
      }),
    onSuccess: (res) => {
      queryClient.setQueryData(["listening-attempt", attemptId], res.attempt);
      setOutcome(res.outcome);
      celebrate(res.outcome);
      ["dashboard", "listening-history", "mistakes"].forEach((k) => queryClient.invalidateQueries({ queryKey: [k] }));
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
    onError: (err) => push({ tone: "error", title: "Couldn't submit your answers", description: errorMessage(err) }),
  });

  if (isLoading) return <PageSkeleton />;
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />;
  const submitted = data.status === "submitted";
  const script = data.script;
  const speakerName = (sid: string) => script.speakers.find((s) => s.id === sid)?.name ?? sid;

  return (
    <div className="space-y-6">
      <div>
        <Link href="/listening" className="text-sm text-muted-foreground hover:text-foreground">
          ← Listening
        </Link>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">{script.title}</h1>
        <p className="text-sm text-muted-foreground">
          {titleCase(script.scenario)} · level {data.difficulty} · {titleCase(script.accent)} accent
        </p>
      </div>
      {data.notice && (
        <Notice tone="default" icon={<Info className="mt-0.5 size-4" />}>
          {data.notice}
        </Notice>
      )}
      {submitted && (
        <Card>
          <CardBody className="flex flex-wrap items-center gap-6">
            <BandValue band={data.band} size="lg" />
            <div>
              <p className="text-2xl font-semibold">
                {data.correct} / {data.total}
              </p>
              <p className="text-sm text-muted-foreground">
                {percent(data.accuracy)} correct · played {data.replays + 1} time{data.replays ? "s" : ""}
              </p>
            </div>
          </CardBody>
        </Card>
      )}
      <SIActions outcome={outcome} />
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4">
          <Card>
            <CardHeader title="The recording" description={script.context} />
            <CardBody className="space-y-4">
              <ListeningPlayer
                segments={script.segments.map((s) => ({ speaker: s.speaker, text: s.text, audio_url: mediaUrl(s.audio_url) }))}
                speakers={script.speakers}
                rate={script.speech_rate}
                mode={script.audio_mode}
                onPlay={(count) => {
                  setPlays(count);
                  if (count > 1 && !submitted) replay.mutate();
                }}
              />
              {!submitted && <p className="text-xs text-muted-foreground">In the real test you hear the recording once. Replays are allowed here but are noted in your results.</p>}
            </CardBody>
          </Card>
          {submitted && (
            <Card>
              <CardHeader title="Transcript" description="Select an answer's evidence to highlight it here." />
              <CardBody className="space-y-2 text-sm leading-relaxed">
                {script.segments.map((seg) => (
                  <p key={seg.index}>
                    <span className="font-semibold">{speakerName(seg.speaker)}:</span> {seg.text ? withEvidence(seg.text, evidence?.evidence ?? null) : null}
                  </p>
                ))}
              </CardBody>
            </Card>
          )}
          {!submitted && script.audio_mode === "device" && (
            <details className="text-sm text-muted-foreground">
              <summary className="cursor-pointer">Audio not playing? Read the transcript instead</summary>
              <div className="mt-2 space-y-1">
                {script.segments.map((seg) => (
                  <p key={seg.index}>
                    <span className="font-medium">{speakerName(seg.speaker)}:</span> {seg.text}
                  </p>
                ))}
              </div>
            </details>
          )}
        </div>
        <div className="space-y-4">
          <Card>
            <CardBody>
              <QuestionForm questions={data.questions} answers={answers} onChange={(qid, v) => setAnswers((a) => ({ ...a, [qid]: v }))} results={submitted ? data.results : undefined} onShowEvidence={setEvidence} />
            </CardBody>
          </Card>
          {!submitted && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                {Object.values(answers).filter((v) => v.trim()).length} of {data.questions.length} answered
              </p>
              <Button size="lg" onClick={() => submit.mutate()} loading={submit.isPending}>
                Submit answers
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
