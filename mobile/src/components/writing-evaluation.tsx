import { router } from "expo-router";
import { ArrowDownRight, ArrowRight, ArrowUpRight, Info } from "lucide-react-native";
import { useMemo, useState } from "react";
import { View } from "react-native";

import { BandValue, CriterionBar } from "@/components/band";
import { Badge, Button, Card, Row, Text } from "@/components/ui";
import { segmentText } from "@/lib/segments";
import { useTheme } from "@/lib/theme";
import type { Submission, WritingErrorItem } from "@/lib/types";
import { formatBand, taskTypeLabel, titleCase } from "@/lib/utils";

function Bullets({ title, items, tone = "primary" }: { title: string; items: string[]; tone?: "primary" | "success" | "warning" }) {
  const { colors } = useTheme();
  if (!items.length) return null;
  const dot = tone === "success" ? colors.success : tone === "warning" ? colors.warning : colors.primary;
  return (
    <View style={{ gap: 6 }}>
      <Text weight="600">{title}</Text>
      {items.map((item) => (
        <View key={item} style={{ flexDirection: "row", gap: 8 }}>
          <View style={{ width: 6, height: 6, borderRadius: 3, marginTop: 8, backgroundColor: dot }} />
          <Text variant="small" style={{ flex: 1 }}>{item}</Text>
        </View>
      ))}
    </View>
  );
}

/** Essay with tappable error highlights (amber for minor issues, red for errors). */
function HighlightedEssay({ text, errors, activeId, onSelect }: { text: string; errors: WritingErrorItem[]; activeId?: number | null; onSelect: (e: WritingErrorItem) => void }) {
  const { colors } = useTheme();
  const segments = useMemo(() => segmentText(text, errors), [text, errors]);
  return (
    <Text style={{ lineHeight: 26 }}>
      {segments.map((segment, i) =>
        segment.error ? (
          <Text
            key={i}
            onPress={() => onSelect(segment.error!)}
            accessibilityRole="button"
            accessibilityLabel={`Error: "${segment.text}". Suggested: "${segment.error.corrected}"`}
            style={{
              lineHeight: 26,
              backgroundColor: activeId === segment.error.id ? colors.primarySoft : segment.error.severity === "low" ? colors.warningSoft : colors.dangerSoft,
              color: activeId === segment.error.id ? colors.primary : segment.error.severity === "low" ? colors.warning : colors.danger,
              textDecorationLine: "underline",
            }}
          >
            {segment.text}
          </Text>
        ) : (
          segment.text
        ),
      )}
    </Text>
  );
}

export function WritingEvaluation({ submission }: { submission: Submission }) {
  const { colors } = useTheme();
  const evaluation = submission.evaluation!;
  const [active, setActive] = useState<WritingErrorItem | null>(evaluation.errors[0] ?? null);
  const previous = submission.previous;
  const metrics = evaluation.metrics as Record<string, number | string | boolean | null>;
  const focus = evaluation.recommended_exercise?.focus;

  return (
    <View style={{ gap: 14 }}>
      <Card>
        <BandValue band={evaluation.overall_band} size="lg" label={evaluation.label} />
        <Text variant="small">{evaluation.summary}</Text>
        <Row wrap gap={6}>
          <Badge label={`${submission.word_count} words`} />
          <Badge label={taskTypeLabel(submission.task.task_type)} />
          <Badge tone={submission.mode === "exam" ? "accent" : "primary"} label={submission.mode === "exam" ? "Exam mode" : "Tutor mode"} />
          {evaluation.is_mock ? <Badge tone="warning" label="Mock AI Mode analysis" /> : null}
        </Row>
        {previous ? (
          <View style={{ backgroundColor: colors.muted, borderRadius: 12, padding: 10, gap: 2 }}>
            <Text variant="label" tone="muted">Compared with your {previous.same_task ? "previous attempt" : "last essay"}</Text>
            <Row gap={4}>
              <Text weight="600">
                {formatBand(previous.overall_band)} → {formatBand(evaluation.overall_band)}
              </Text>
              {evaluation.overall_band > previous.overall_band ? (
                <ArrowUpRight size={16} color={colors.success} accessibilityLabel="higher" />
              ) : evaluation.overall_band < previous.overall_band ? (
                <ArrowDownRight size={16} color={colors.danger} accessibilityLabel="lower" />
              ) : null}
            </Row>
          </View>
        ) : null}
        <Text variant="caption" tone="muted">{evaluation.disclaimer}</Text>
      </Card>

      <Card>
        <Text variant="subheading">Your response</Text>
        <Text variant="small" tone="muted">
          {evaluation.errors.length ? `${evaluation.errors.length} issue${evaluation.errors.length === 1 ? "" : "s"} highlighted — tap one to see the correction.` : "No language errors were detected in this response."}
        </Text>
        <HighlightedEssay text={submission.content} errors={evaluation.errors} activeId={active?.id} onSelect={setActive} />
      </Card>

      {active ? (
        <Card style={{ borderColor: colors.primary + "55" }}>
          <Row wrap>
            <Badge tone={active.severity === "high" ? "danger" : active.severity === "medium" ? "warning" : "muted"} label={titleCase(active.subcategory)} />
            {active.repeated ? <Badge tone="danger" label="Repeated mistake" /> : null}
          </Row>
          <Text>
            <Text style={{ color: colors.danger, textDecorationLine: "line-through" }}>{active.original}</Text>
            {"  →  "}
            <Text weight="600" tone="success">{active.corrected}</Text>
          </Text>
          <Text variant="small" tone="muted">{active.explanation}</Text>
          {active.mistake_id ? <Button title="Saved to My Mistakes" variant="ghost" size="sm" icon={ArrowRight} onPress={() => router.push(`/mistakes?focus=${active.mistake_id}`)} style={{ alignSelf: "flex-start" }} /> : null}
        </Card>
      ) : null}

      <Card>
        <Text variant="subheading">Criteria</Text>
        <Text variant="caption" tone="muted">Each IELTS-style criterion is estimated separately.</Text>
        {evaluation.criteria.map((c) => (
          <CriterionBar key={c.key} label={c.label} band={c.band} comment={c.comment} />
        ))}
      </Card>

      <Card style={{ gap: 14 }}>
        <Bullets title="Strengths" items={evaluation.strengths} tone="success" />
        <Bullets title="To improve" items={evaluation.weaknesses} tone="warning" />
        <Bullets title="Task response" items={evaluation.task_response_issues} />
        <Bullets title="Coherence & cohesion" items={evaluation.cohesion_issues} />
        <Bullets title="Vocabulary" items={evaluation.vocabulary_issues} />
      </Card>

      <Card style={{ gap: 14 }}>
        <Text variant="subheading">Your next steps</Text>
        <Bullets title="Advice" items={evaluation.advice} />
        {focus ? (
          <View style={{ backgroundColor: colors.primarySoft, borderRadius: 14, padding: 12, gap: 6 }}>
            <Text weight="600">{evaluation.recommended_exercise.title}</Text>
            <Text variant="small" tone="muted">{evaluation.recommended_exercise.description}</Text>
            <Button title="Practise now" size="sm" onPress={() => router.push(`/practice/new?focus=${focus}`)} style={{ alignSelf: "flex-start" }} />
          </View>
        ) : null}
        <Row wrap gap={8}>
          {(
            [
              ["Paragraphs", metrics.paragraph_count],
              ["Avg. sentence", metrics.avg_sentence_length ? `${metrics.avg_sentence_length} words` : null],
              ["Lexical diversity", metrics.lexical_diversity],
              ["Linking words", metrics.linker_variety],
            ] as const
          ).map(([label, value]) => (
            <View key={label} style={{ backgroundColor: colors.muted, borderRadius: 12, padding: 10, minWidth: "47%", flexGrow: 1 }}>
              <Text variant="caption" tone="muted">{label}</Text>
              <Text weight="600">{value === null || value === undefined ? "—" : String(value)}</Text>
            </View>
          ))}
        </Row>
        <Row style={{ alignItems: "flex-start" }}>
          <Info size={13} color={colors.mutedForeground} style={{ marginTop: 2 }} />
          <Text variant="caption" tone="muted" style={{ flex: 1 }}>
            Evaluated by {evaluation.is_mock ? "LinguaSI's built-in analysis (Mock AI Mode)" : `${evaluation.provider} · ${evaluation.model}`}
          </Text>
        </Row>
      </Card>
    </View>
  );
}
