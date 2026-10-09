import { useMutation, useQuery } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { Clock, Mic, Keyboard } from "lucide-react-native";
import { useState } from "react";
import { ActivityIndicator } from "react-native";

import { BandValue } from "@/components/band";
import { useToast } from "@/components/toast";
import { Badge, Button, Card, EmptyState, ErrorState, ListRow, Notice, Row, Screen, Text } from "@/components/ui";
import { useMeta } from "@/hooks/use-meta";
import { useRefetchOnFocus } from "@/hooks/use-refetch-on-focus";
import { api, errorMessage } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import type { Page, SpeakingSession, SpeakingSummary } from "@/lib/types";
import { formatDate, formatDuration } from "@/lib/utils";

const MODES = [
  { value: "full", title: "Full mock test", minutes: "11–14 min", text: "Parts 1, 2 and 3 with follow-up questions, like the real test." },
  { value: "part1", title: "Part 1", minutes: "4–5 min", text: "Familiar topics: home, work, studies and interests." },
  { value: "part2", title: "Part 2", minutes: "3–4 min", text: "A cue card with one minute to prepare and up to two minutes to talk." },
  { value: "part3", title: "Part 3", minutes: "4–5 min", text: "A deeper discussion of abstract ideas linked to a topic." },
] as const;

export default function SpeakingHub() {
  const { mode: recommended } = useLocalSearchParams<{ mode?: string }>();
  const { colors } = useTheme();
  const { push } = useToast();
  const meta = useMeta();
  const [starting, setStarting] = useState<string | null>(null);
  const history = useQuery({ queryKey: ["speaking-history"], queryFn: () => api<Page<SpeakingSummary>>("/speaking/history?page_size=20") });
  useRefetchOnFocus(history.refetch);
  const start = useMutation({
    mutationFn: (mode: string) => api<{ session: SpeakingSession }>("/speaking/session/start", { json: { mode } }),
    onMutate: (mode) => setStarting(mode),
    onSuccess: (res) => {
      setStarting(null);
      router.push(`/speaking/${res.session.id}`);
    },
    onError: (err) => {
      setStarting(null);
      push({ tone: "error", title: "Couldn't start the test", description: errorMessage(err) });
    },
  });
  const serverStt = meta.data ? meta.data.speech.stt_provider !== "mock" : null;

  return (
    <Screen refreshing={history.isRefetching} onRefresh={history.refetch}>
      <Text tone="muted">IELTS-style speaking with an AI examiner: record your answers, get follow-up questions, and receive an AI estimated evaluation at the end.</Text>
      {serverStt === false ? (
        <Notice tone="primary" icon={Keyboard}>
          Server transcription is off (Mock AI Mode). Your recordings are kept for replay, and you type — or dictate with your keyboard — what you said. Pronunciation is then not scored.
        </Notice>
      ) : null}
      {MODES.map((m) => (
        <Card key={m.value} style={recommended === m.value ? { borderColor: colors.primary, borderWidth: 2 } : undefined}>
          <Row style={{ justifyContent: "space-between" }}>
            <Text weight="600">{m.title}</Text>
            {recommended === m.value ? (
              <Badge tone="primary" label="Recommended for you" />
            ) : (
              <Row gap={4}>
                <Clock size={12} color={colors.mutedForeground} />
                <Text variant="caption" tone="muted">{m.minutes}</Text>
              </Row>
            )}
          </Row>
          <Text variant="small" tone="muted">{m.text}</Text>
          <Button title="Start" icon={Mic} size="sm" loading={starting === m.value} disabled={!!starting} onPress={() => start.mutate(m.value)} style={{ alignSelf: "flex-start" }} />
        </Card>
      ))}
      <Card style={{ gap: 0, paddingVertical: 4 }}>
        <Text variant="subheading" style={{ paddingTop: 10 }}>Previous tests</Text>
        {history.isLoading ? (
          <ActivityIndicator />
        ) : history.error ? (
          <ErrorState error={history.error} onRetry={() => history.refetch()} />
        ) : history.data?.items.length ? (
          history.data.items.map((s) => (
            <ListRow
              key={s.id}
              title={s.topic}
              subtitle={`${s.mode === "full" ? "Full test" : `Part ${s.mode.slice(-1)}`} · ${s.responses} answers · ${formatDuration(s.total_speaking_seconds)} · ${formatDate(s.created_at)}`}
              right={s.overall_band !== null ? <BandValue band={s.overall_band} size="sm" label={null} /> : <Badge label={s.status === "in_progress" ? "In progress" : s.status.replace("_", " ")} />}
              onPress={() => router.push(`/speaking/${s.id}`)}
            />
          ))
        ) : (
          <EmptyState title="No speaking tests yet" description="Start with Part 1 to warm up — it takes about five minutes." />
        )}
      </Card>
    </Screen>
  );
}
