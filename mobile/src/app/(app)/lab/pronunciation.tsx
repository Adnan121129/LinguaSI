import { useMutation, useQuery } from "@tanstack/react-query";
import { Info, Volume2 } from "lucide-react-native";
import { useRef, useState } from "react";
import { ScrollView, View } from "react-native";

import { useToast } from "@/components/toast";
import { Badge, Button, Card, Chip, Input, Notice, ProgressBar, QueryView, Row, Screen, Text } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { speak } from "@/lib/speech";
import { useTheme } from "@/lib/theme";
import type { PronunciationResult } from "@/lib/types";

type PronunciationSet = { focus: string; title: string; sentences: string[] };

/**
 * Listen, then say the sentence using the keyboard's dictation key: the phone's own speech
 * recognition writes what it heard, and the server compares it with the sentence. It is a clarity
 * check (which words were understood), not a phonetic pronunciation score.
 */
function SentencePractice({ sentence }: { sentence: string }) {
  const { colors } = useTheme();
  const { push, celebrate } = useToast();
  const [heard, setHeard] = useState("");
  const startedAt = useRef<number | null>(null);
  const check = useMutation({
    mutationFn: (transcript: string) =>
      api<PronunciationResult>("/lab/pronunciation/check", {
        json: { sentence, transcript, duration_seconds: startedAt.current ? Math.min(120, (Date.now() - startedAt.current) / 1000) : null },
      }),
    onSuccess: (res) => celebrate(res.outcome),
    onError: (err) => push({ tone: "error", title: "Couldn't check that attempt", description: errorMessage(err) }),
  });
  const result = check.data;
  const missing = new Set(result?.missing_words.map((w) => w.toLowerCase()));

  return (
    <View style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 14, padding: 12, gap: 10 }}>
      <Text variant="subheading" weight="400">
        {sentence.split(" ").map((word, i) => {
          const clean = word.replace(/[^A-Za-z']/g, "").toLowerCase();
          const miss = !!result && missing.has(clean);
          return (
            <Text key={i} variant="subheading" weight="400" style={miss ? { color: colors.danger, backgroundColor: colors.dangerSoft } : undefined}>
              {word}{" "}
            </Text>
          );
        })}
      </Text>
      <Button title="Listen" icon={Volume2} size="sm" variant="outline" onPress={() => speak(sentence, { rate: 0.9 })} style={{ alignSelf: "flex-start" }} />
      <Input
        value={heard}
        onChangeText={(v) => {
          if (!startedAt.current) startedAt.current = Date.now();
          setHeard(v);
        }}
        multiline
        placeholder="Tap here, then the 🎤 key on your keyboard, and read the sentence aloud"
        accessibilityLabel="What speech recognition heard"
      />
      <Button title="Check" size="sm" disabled={!heard.trim()} loading={check.isPending} onPress={() => check.mutate(heard.trim())} style={{ alignSelf: "flex-start" }} />
      {result ? (
        <View style={{ gap: 6 }}>
          <Row>
            <Badge tone={result.match >= 90 ? "success" : result.match >= 70 ? "primary" : "warning"} label={`${Math.round(result.match)}% understood`} />
          </Row>
          <ProgressBar value={result.match} tone={result.match >= 90 ? "success" : "primary"} label="Words recognised" />
          <Text variant="small">{result.tip}</Text>
          {result.unexpected_words.length ? <Text variant="small" tone="muted">Heard instead: {result.unexpected_words.join(", ")}</Text> : null}
        </View>
      ) : null}
    </View>
  );
}

export default function PronunciationScreen() {
  const sets = useQuery({ queryKey: ["pronunciation-sets"], queryFn: () => api<PronunciationSet[]>("/lab/pronunciation") });
  const [focus, setFocus] = useState<string | null>(null);
  return (
    <QueryView query={sets}>
      {(data) => {
        const current = data.find((s) => s.focus === focus) ?? data[0];
        return (
          <Screen>
            <Notice tone="muted" icon={Info}>
              Say each sentence with your keyboard&apos;s dictation. This is a clarity check — it compares what your phone&apos;s speech recognition heard with the sentence — not a phonetic pronunciation score.
            </Notice>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
              {data.map((s) => (
                <Chip key={s.focus} label={s.title.split(" ").slice(0, 3).join(" ")} selected={current.focus === s.focus} onPress={() => setFocus(s.focus)} />
              ))}
            </ScrollView>
            <Card>
              <Text variant="subheading">{current.title}</Text>
              {current.sentences.map((sentence) => (
                <SentencePractice key={sentence} sentence={sentence} />
              ))}
            </Card>
          </Screen>
        );
      }}
    </QueryView>
  );
}
