import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, ChevronLeft, GraduationCap, Languages } from "lucide-react-native";
import { useState } from "react";
import { Pressable, ScrollView, View } from "react-native";

import { useToast } from "@/components/toast";
import { Button, Card, Chip, Input, ProgressBar, Row, Screen, Text } from "@/components/ui";
import { useMe } from "@/hooks/use-me";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { BANDS, LEVELS, TOPICS } from "@/lib/constants";
import { setPendingRoute } from "@/lib/pending-route";
import { checkTestDate } from "@/lib/validation";
import { useTheme } from "@/lib/theme";
import type { User } from "@/lib/types";
import { titleCase } from "@/lib/utils";

type Form = {
  goal: "ielts" | "general";
  ielts_module: "academic" | "general_training";
  target_band: number;
  test_date: string;
  self_reported_level: string;
  confidence: number;
  daily_minutes: number;
  preferred_mode: "guided" | "balanced" | "exam";
  preferred_topics: string[];
};

const MINUTES = [10, 15, 20, 30, 45, 60, 90];
const MODES = [
  ["guided", "Guided", "More hints and explanations"],
  ["balanced", "Balanced", "A mix of help and challenge"],
  ["exam", "Exam-like", "Timed, realistic conditions"],
] as const;

function Choice({ selected, onPress, title, text, icon }: { selected: boolean; onPress: () => void; title: string; text: string; icon?: React.ReactNode }) {
  const { colors } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="radio"
      accessibilityState={{ checked: selected }}
      style={{ flexDirection: "row", gap: 12, borderWidth: 1, borderRadius: 16, padding: 14, borderColor: selected ? colors.primary : colors.border, backgroundColor: selected ? colors.primarySoft : colors.card }}
    >
      {icon}
      <View style={{ flex: 1, gap: 2 }}>
        <Text weight="600">{title}</Text>
        <Text variant="small" tone="muted">{text}</Text>
      </View>
    </Pressable>
  );
}

export default function OnboardingScreen() {
  const { colors } = useTheme();
  const { data: me } = useMe();
  const { signOut } = useAuth();
  const { push } = useToast();
  const queryClient = useQueryClient();
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<Form>({
    goal: "ielts",
    ielts_module: "academic",
    target_band: 7.0,
    test_date: "",
    self_reported_level: "intermediate",
    confidence: 3,
    daily_minutes: 30,
    preferred_mode: "balanced",
    preferred_topics: ["technology", "education"],
  });
  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm((f) => ({ ...f, [key]: value }));
  const dateError = form.goal === "ielts" ? checkTestDate(form.test_date.trim()) : null;
  const steps = ["Goal", "Level", "Routine"];

  async function finish(takeDiagnostic: boolean) {
    setSaving(true);
    try {
      const user = await api<User>("/onboarding", {
        json: {
          ...form,
          test_date: form.goal === "ielts" && form.test_date.trim() ? form.test_date.trim() : null,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          name: me?.name,
        },
      });
      setPendingRoute(takeDiagnostic ? "/diagnostic" : null);
      push({ tone: "success", title: "Your learning plan is ready", description: takeDiagnostic ? "Let's measure your starting level." : undefined });
      queryClient.setQueryData(["me"], user); // unlocks the app; the layout opens the diagnostic if chosen
    } catch (err) {
      push({ tone: "error", title: "Couldn't save your preferences", description: errorMessage(err) });
      setSaving(false);
    }
  }

  return (
    <Screen safeTop>
      <View style={{ gap: 6 }}>
        <Text tone="primary" weight="600">Welcome{me ? `, ${me.name.split(" ")[0]}` : ""}</Text>
        <Text variant="title">Let&apos;s personalise LinguaSI for you</Text>
        <Row>
          <View style={{ flex: 1 }}>
            <ProgressBar value={((step + 1) / steps.length) * 100} label="Onboarding progress" />
          </View>
          <Text variant="caption" tone="muted">Step {step + 1} of {steps.length}</Text>
        </Row>
      </View>

      <Card style={{ gap: 14 }}>
        {step === 0 ? (
          <>
            <Text variant="subheading">What is your main goal?</Text>
            <Choice selected={form.goal === "ielts"} onPress={() => set("goal", "ielts")} title="Prepare for IELTS" text="IELTS-style practice with AI estimated bands." icon={<GraduationCap size={20} color={colors.primary} />} />
            <Choice selected={form.goal === "general"} onPress={() => set("goal", "general")} title="Improve my English" text="Everyday and work English with the English Lab." icon={<Languages size={20} color={colors.primary} />} />
            {form.goal === "ielts" ? (
              <>
                <Text variant="small" weight="600">Module</Text>
                <Row wrap>
                  <Chip label="Academic" selected={form.ielts_module === "academic"} onPress={() => set("ielts_module", "academic")} />
                  <Chip label="General Training" selected={form.ielts_module === "general_training"} onPress={() => set("ielts_module", "general_training")} />
                </Row>
                <Text variant="small" weight="600">Target band</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
                  {BANDS.map((b) => (
                    <Chip key={b} label={b.toFixed(1)} selected={form.target_band === b} onPress={() => set("target_band", b)} />
                  ))}
                </ScrollView>
                <Input
                  label="Test date (optional)"
                  value={form.test_date}
                  onChangeText={(v) => set("test_date", v)}
                  placeholder="YYYY-MM-DD"
                  autoCapitalize="none"
                  keyboardType="numbers-and-punctuation"
                  maxLength={10}
                  error={dateError ?? undefined}
                  hint="Leave empty if you haven't booked yet."
                />
              </>
            ) : null}
          </>
        ) : null}

        {step === 1 ? (
          <>
            <Text variant="subheading">How would you describe your English today?</Text>
            {LEVELS.map((level) => (
              <Choice key={level.value} selected={form.self_reported_level === level.value} onPress={() => set("self_reported_level", level.value)} title={level.label} text={level.hint} />
            ))}
            <Text variant="small" weight="600">How confident do you feel speaking English? ({form.confidence}/5)</Text>
            <Row wrap>
              {[1, 2, 3, 4, 5].map((n) => (
                <Chip key={n} label={String(n)} selected={form.confidence === n} onPress={() => set("confidence", n)} />
              ))}
            </Row>
          </>
        ) : null}

        {step === 2 ? (
          <>
            <Text variant="subheading">Your study routine</Text>
            <Text variant="small" weight="600">Daily study time: {form.daily_minutes} minutes</Text>
            <Row wrap>
              {MINUTES.map((m) => (
                <Chip key={m} label={`${m} min`} selected={form.daily_minutes === m} onPress={() => set("daily_minutes", m)} />
              ))}
            </Row>
            <Text variant="caption" tone="muted">Your daily mission is sized to fit this.</Text>
            <Text variant="small" weight="600">Preferred style</Text>
            {MODES.map(([value, title, text]) => (
              <Choice key={value} selected={form.preferred_mode === value} onPress={() => set("preferred_mode", value)} title={title} text={text} />
            ))}
            <Text variant="small" weight="600">Topics you enjoy</Text>
            <Row wrap>
              {TOPICS.map((t) => {
                const on = form.preferred_topics.includes(t);
                return <Chip key={t} label={titleCase(t)} selected={on} onPress={() => set("preferred_topics", on ? form.preferred_topics.filter((x) => x !== t) : [...form.preferred_topics, t])} />;
              })}
            </Row>
          </>
        ) : null}
      </Card>

      <Row style={{ justifyContent: "space-between" }}>
        {step > 0 ? <Button title="Back" variant="ghost" icon={ChevronLeft} onPress={() => setStep((s) => s - 1)} /> : <Button title="Sign out" variant="ghost" onPress={signOut} />}
        {step < steps.length - 1 ? <Button title="Continue" icon={ArrowRight} disabled={!!dateError} onPress={() => setStep((s) => s + 1)} /> : null}
      </Row>
      {step === steps.length - 1 ? (
        <View style={{ gap: 10 }}>
          <Button title="Save and take the diagnostic" size="lg" loading={saving} onPress={() => finish(true)} />
          <Button title="Skip the diagnostic for now" variant="outline" disabled={saving} onPress={() => finish(false)} />
          <Text variant="caption" tone="muted" style={{ textAlign: "center" }}>The diagnostic takes about 15 minutes and gives you an AI estimated level.</Text>
        </View>
      ) : null}
    </Screen>
  );
}
