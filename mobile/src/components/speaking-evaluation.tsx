import { Info } from "lucide-react-native";
import { View } from "react-native";

import { AudioButton } from "@/components/audio-button";
import { BandValue, CriterionBar } from "@/components/band";
import { Badge, Card, Row, Text } from "@/components/ui";
import { useTheme } from "@/lib/theme";
import type { SpeakingSession } from "@/lib/types";
import { formatDuration, titleCase } from "@/lib/utils";

function Bullets({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <View style={{ gap: 4 }}>
      <Text weight="600">{title}</Text>
      {items.map((item) => (
        <Text key={item} variant="small">
          • {item}
        </Text>
      ))}
    </View>
  );
}

export function SpeakingEvaluation({ session }: { session: SpeakingSession }) {
  const { colors } = useTheme();
  const ev = session.evaluation!;
  const metrics = ev.metrics as Record<string, number | boolean | null>;
  const criteria = ["fluency_coherence", "lexical_resource", "grammatical_range_accuracy", "pronunciation"] as const;
  const measurements: [string, string][] = [
    ["Speaking speed", metrics.avg_wpm ? `${Math.round(Number(metrics.avg_wpm))} words/min` : "—"],
    ["Hesitation", titleCase(ev.hesitation.level)],
    [ev.hesitation.measured ? "Pauses (measured)" : "Pauses (estimated)", `${ev.hesitation.pauses} · ${ev.hesitation.long_pauses} long`],
    ["Filler words", `${ev.fillers.per_minute}/min`],
    ["Developed answers", metrics.developed_ratio !== undefined && metrics.developed_ratio !== null ? `${Math.round(Number(metrics.developed_ratio) * 100)}%` : "—"],
    ["Word variety", metrics.lexical_variety === undefined || metrics.lexical_variety === null ? "—" : String(metrics.lexical_variety)],
  ];

  return (
    <View style={{ gap: 14 }}>
      <Card>
        <BandValue band={ev.overall_band} size="lg" label={ev.label} />
        <Text variant="small">{ev.summary}</Text>
        <Row wrap gap={6}>
          <Badge label={session.mode === "full" ? "Full mock test" : `Part ${session.mode.slice(-1)}`} />
          <Badge label={`${session.transcripts.length} answers`} />
          <Badge label={`${formatDuration(session.total_speaking_seconds)} speaking`} />
          {ev.is_mock ? <Badge tone="warning" label="Mock AI Mode analysis" /> : null}
        </Row>
        <Text variant="caption" tone="muted">{ev.disclaimer}</Text>
      </Card>

      <Card>
        <Text variant="subheading">Criteria</Text>
        <Text variant="caption" tone="muted">Estimated from your transcripts and measured speech features.</Text>
        {criteria.map((key) => {
          const fb = ev.criteria_feedback[key];
          const band = key === "pronunciation" ? ev.pronunciation : ev[key];
          return <CriterionBar key={key} label={fb?.label ?? key} band={band} comment={fb?.comment} />;
        })}
        {ev.pronunciation === null ? (
          <Row style={{ alignItems: "flex-start", backgroundColor: colors.muted, borderRadius: 12, padding: 10 }}>
            <Info size={14} color={colors.mutedForeground} style={{ marginTop: 2 }} />
            <Text variant="caption" tone="muted" style={{ flex: 1 }}>{ev.pronunciation_note}</Text>
          </Row>
        ) : null}
      </Card>

      <Card>
        <Text variant="subheading">Fluency measurements</Text>
        <Text variant="caption" tone="muted">{ev.hesitation.note}</Text>
        <Row wrap gap={8}>
          {measurements.map(([label, value]) => (
            <View key={label} style={{ backgroundColor: colors.muted, borderRadius: 12, padding: 10, minWidth: "47%", flexGrow: 1 }}>
              <Text variant="caption" tone="muted">{label}</Text>
              <Text weight="600">{value}</Text>
            </View>
          ))}
        </Row>
        {ev.repeated_words.length ? <Text variant="small" tone="muted">Most repeated words: {ev.repeated_words.slice(0, 5).map((w) => `${w.word} (${w.count})`).join(", ")}</Text> : null}
        <Text variant="caption" tone="muted">{ev.fillers.note}</Text>
      </Card>

      <Card style={{ gap: 14 }}>
        <Bullets title="Strengths" items={ev.strengths} />
        <Bullets title="To improve" items={ev.weaknesses} />
        <Bullets title="Grammar patterns" items={ev.grammar_patterns} />
        <Bullets title="Practice recommendations" items={ev.recommendations} />
        <Bullets title="Target expressions you used" items={ev.expressions_used} />
      </Card>

      {ev.errors.length ? (
        <Card>
          <Text variant="subheading">Language to fix</Text>
          <Text variant="caption" tone="muted">These are saved to My Mistakes.</Text>
          {ev.errors.map((e, i) => (
            <Text key={i} variant="small">
              <Text variant="small" style={{ color: colors.danger, textDecorationLine: "line-through" }}>{e.original}</Text>
              {"  →  "}
              <Text variant="small" tone="success" weight="600">{e.corrected}</Text>
              <Text variant="small" tone="muted"> — {e.explanation}</Text>
            </Text>
          ))}
        </Card>
      ) : null}

      <Card>
        <Text variant="subheading">Your answers</Text>
        <Text variant="caption" tone="muted">Replay your recordings and read the transcripts.</Text>
        {session.transcripts.map((t) => (
          <View key={t.id} style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 14, padding: 12, gap: 6 }}>
            <Text variant="label" tone="muted">
              Part {t.part}
              {t.is_followup ? " · follow-up" : ""} · {Math.round(t.duration_seconds)}s · {t.word_count} words · {t.transcript_source === "typed" ? "typed" : "spoken"}
            </Text>
            <Text weight="600">{t.question}</Text>
            <Text variant="small">{t.transcript}</Text>
            {t.has_audio && t.audio_url ? <AudioButton path={t.audio_url} /> : null}
          </View>
        ))}
      </Card>
    </View>
  );
}
