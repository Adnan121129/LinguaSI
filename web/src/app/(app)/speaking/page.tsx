"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Clock, Mic, MicOff } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, useSyncExternalStore } from "react";

import { BandValue } from "@/components/band";
import { useToast } from "@/components/providers/toast";
import { Badge, Button, Card, CardBody, CardHeader, EmptyState, ErrorState, Notice, PageHeader, Skeleton } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { recognitionSupported } from "@/lib/speech";
import type { Page, SpeakingSession, SpeakingSummary } from "@/lib/types";
import { cn, formatDate, formatDuration } from "@/lib/utils";

const MODES = [
  { value: "full", title: "Full mock test", minutes: "11–14 min", text: "Parts 1, 2 and 3 with follow-up questions, like the real test." },
  { value: "part1", title: "Part 1", minutes: "4–5 min", text: "Familiar topics: home, work, studies and interests." },
  { value: "part2", title: "Part 2", minutes: "3–4 min", text: "A cue card with one minute to prepare and up to two minutes to talk." },
  { value: "part3", title: "Part 3", minutes: "4–5 min", text: "A deeper discussion of abstract ideas linked to a topic." },
] as const;

const subscribe = () => () => {};

function SpeakingHub() {
  const params = useSearchParams();
  const router = useRouter();
  const { push } = useToast();
  const recommended = params.get("mode");
  const [starting, setStarting] = useState<string | null>(null);
  const liveTranscription = useSyncExternalStore(subscribe, recognitionSupported, () => true);
  const history = useQuery({ queryKey: ["speaking-history"], queryFn: () => api<Page<SpeakingSummary>>("/speaking/history?page_size=20") });

  const start = useMutation({
    mutationFn: (mode: string) => api<{ session: SpeakingSession }>("/speaking/session/start", { json: { mode } }),
    onMutate: (mode) => setStarting(mode),
    onSuccess: (res) => router.push(`/speaking/${res.session.id}`),
    onError: (err) => {
      setStarting(null);
      push({ tone: "error", title: "Couldn't start the test", description: errorMessage(err) });
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Speaking" description="IELTS-style speaking practice with an AI examiner. Record your answers (or type them), get follow-up questions, and receive an AI estimated evaluation at the end." />
      {!liveTranscription && (
        <Notice tone="warning" icon={<MicOff className="mt-0.5 size-4 text-warning" />}>
          This browser doesn&apos;t offer live speech recognition. You can still record your answers and then type what you said — or use Chrome or Edge for automatic transcripts.
        </Notice>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {MODES.map((m) => (
          <Card key={m.value} className={cn(recommended === m.value && "border-primary ring-2 ring-primary/20")}>
            <CardBody className="flex h-full flex-col gap-3">
              <div className="flex items-center justify-between">
                <p className="font-semibold">{m.title}</p>
                {recommended === m.value ? <Badge tone="primary">Recommended for you</Badge> : <Badge>
                  <Clock className="size-3" /> {m.minutes}
                </Badge>}
              </div>
              <p className="text-sm text-muted-foreground">{m.text}</p>
              <Button className="mt-auto w-fit" onClick={() => start.mutate(m.value)} loading={starting === m.value} disabled={!!starting}>
                <Mic className="size-4" /> Start
              </Button>
            </CardBody>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader title="Previous tests" />
        <CardBody>
          {history.isLoading ? (
            <Skeleton className="h-32" />
          ) : history.error ? (
            <ErrorState error={history.error} onRetry={() => history.refetch()} />
          ) : history.data?.items.length ? (
            <ul className="divide-y divide-border">
              {history.data.items.map((s) => (
                <li key={s.id}>
                  <Link href={`/speaking/${s.id}`} className="flex flex-wrap items-center gap-4 py-3 hover:bg-muted/40">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">{s.topic}</p>
                      <p className="text-sm text-muted-foreground">
                        {s.mode === "full" ? "Full test" : `Part ${s.mode.slice(-1)}`} · {s.responses} answers · {formatDuration(s.total_speaking_seconds)} · {formatDate(s.created_at)}
                      </p>
                    </div>
                    {s.overall_band !== null ? <BandValue band={s.overall_band} size="sm" label={null} /> : <Badge>{s.status === "in_progress" ? "In progress" : s.status.replace("_", " ")}</Badge>}
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="No speaking tests yet" description="Start with Part 1 to warm up — it takes about five minutes." />
          )}
        </CardBody>
      </Card>
    </div>
  );
}

export default function SpeakingPage() {
  return (
    <Suspense>
      <SpeakingHub />
    </Suspense>
  );
}
