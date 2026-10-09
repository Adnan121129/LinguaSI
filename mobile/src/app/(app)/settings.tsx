import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { ScrollView, Switch, View } from "react-native";

import { ThemeToggle } from "@/components/theme-toggle";
import { useToast } from "@/components/toast";
import { Button, Card, Chip, Input, Loading, Notice, Row, Screen, Text } from "@/components/ui";
import { useMe, useUpdateProfile } from "@/hooks/use-me";
import { api, errorMessage, fieldErrors } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { confirmAction } from "@/lib/confirm";
import { BANDS, LEVELS, TOPICS } from "@/lib/constants";
import { useTheme } from "@/lib/theme";
import type { Profile, User } from "@/lib/types";
import { titleCase } from "@/lib/utils";
import { checkTestDate } from "@/lib/validation";

const MINUTES = [10, 15, 20, 30, 45, 60, 90, 120];

function SettingsForm({ me }: { me: User }) {
  const { colors } = useTheme();
  const { signOut } = useAuth();
  const update = useUpdateProfile();
  const { push } = useToast();
  const [form, setForm] = useState<Partial<Profile> & { name?: string }>(() => ({ ...me.profile, name: me.name }));
  const [passwords, setPasswords] = useState({ current: "", next: "" });
  const [deletePassword, setDeletePassword] = useState("");
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm((f) => ({ ...f, [key]: value }));
  const dateError = form.goal === "ielts" ? checkTestDate((form.test_date ?? "").trim()) : null;

  const changePassword = useMutation({
    mutationFn: () => api("/me/change-password", { json: { current_password: passwords.current, new_password: passwords.next } }),
    onSuccess: () => {
      push({ tone: "success", title: "Password changed", description: "Your other devices have been signed out." });
      setPasswords({ current: "", next: "" });
    },
    onError: (err) => push({ tone: "error", title: "Password not changed", description: Object.values(fieldErrors(err))[0] ?? errorMessage(err) }),
  });
  const deleteAccount = useMutation({
    mutationFn: () => api("/me/delete", { json: { password: deletePassword } }),
    onSuccess: () => {
      push({ tone: "success", title: "Account deleted", description: "Your account and learning data have been removed." });
      signOut();
    },
    onError: (err) => push({ tone: "error", title: "Account not deleted", description: errorMessage(err) }),
  });

  function save() {
    const { name, goal, ielts_module, self_reported_level, target_band, test_date, daily_minutes, preferred_mode, confidence, preferred_topics, timezone, keep_recordings } = form;
    const date = (test_date ?? "").trim();
    update.mutate(
      { name, goal, ielts_module, self_reported_level, target_band, daily_minutes, preferred_mode, confidence, preferred_topics, timezone, keep_recordings, ...(date ? { test_date: date } : { clear_test_date: true }) },
      {
        onSuccess: () => push({ tone: "success", title: "Settings saved", description: "Your plan and recommendations will adapt." }),
        onError: (err) => push({ tone: "error", title: "Settings not saved", description: errorMessage(err) }),
      },
    );
  }

  return (
    <Screen>
      <Text tone="muted">{me.email}</Text>
      <Card>
        <Text variant="subheading">Appearance</Text>
        <Text variant="caption" tone="muted">Light, dark, or follow your phone. Saved to your account.</Text>
        <ThemeToggle />
      </Card>

      <Card>
        <Text variant="subheading">Learning profile</Text>
        <Text variant="caption" tone="muted">SI uses these to plan missions and choose content.</Text>
        <Input label="Name" value={form.name ?? ""} onChangeText={(v) => set("name", v)} maxLength={100} />
        <Text variant="small" weight="600">Goal</Text>
        <Row wrap>
          <Chip label="IELTS preparation" selected={form.goal === "ielts"} onPress={() => set("goal", "ielts")} />
          <Chip label="General English" selected={form.goal === "general"} onPress={() => set("goal", "general")} />
        </Row>
        {form.goal === "ielts" ? (
          <>
            <Text variant="small" weight="600">IELTS module</Text>
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
              label="Test date"
              value={form.test_date ?? ""}
              onChangeText={(v) => set("test_date", v || null)}
              placeholder="YYYY-MM-DD"
              autoCapitalize="none"
              keyboardType="numbers-and-punctuation"
              maxLength={10}
              error={dateError ?? undefined}
              hint="Leave empty if you haven't booked yet."
            />
          </>
        ) : null}
        <Text variant="small" weight="600">Self-assessed level</Text>
        <Row wrap>
          {LEVELS.map((l) => (
            <Chip key={l.value} label={l.label} selected={form.self_reported_level === l.value} onPress={() => set("self_reported_level", l.value)} />
          ))}
        </Row>
        <Text variant="small" weight="600">Daily study time: {form.daily_minutes} min</Text>
        <Row wrap>
          {MINUTES.map((m) => (
            <Chip key={m} label={`${m}`} selected={form.daily_minutes === m} onPress={() => set("daily_minutes", m)} />
          ))}
        </Row>
        <Text variant="small" weight="600">Preferred style</Text>
        <Row wrap>
          {(["guided", "balanced", "exam"] as const).map((mode) => (
            <Chip key={mode} label={mode === "exam" ? "Exam-like" : titleCase(mode)} selected={form.preferred_mode === mode} onPress={() => set("preferred_mode", mode)} />
          ))}
        </Row>
        <Input label="Time zone" value={form.timezone ?? ""} onChangeText={(v) => set("timezone", v)} autoCapitalize="none" hint="Used for streaks and daily missions, e.g. Europe/London." />
        <Text variant="small" weight="600">Topics you enjoy</Text>
        <Row wrap>
          {TOPICS.map((t) => {
            const on = !!form.preferred_topics?.includes(t);
            return <Chip key={t} label={titleCase(t)} selected={on} onPress={() => set("preferred_topics", on ? (form.preferred_topics ?? []).filter((x) => x !== t) : [...(form.preferred_topics ?? []), t])} />;
          })}
        </Row>
        <Row style={{ justifyContent: "space-between" }}>
          <Text variant="small" style={{ flex: 1 }}>Keep my speaking recordings so I can replay them (off: transcripts only)</Text>
          <Switch value={!!form.keep_recordings} onValueChange={(v) => set("keep_recordings", v)} trackColor={{ true: colors.primary, false: colors.border }} accessibilityLabel="Keep speaking recordings" />
        </Row>
        <Button title="Save changes" loading={update.isPending} disabled={!!dateError} onPress={save} />
      </Card>

      <Card>
        <Text variant="subheading">Password</Text>
        <Input label="Current password" value={passwords.current} onChangeText={(v) => setPasswords((p) => ({ ...p, current: v }))} secureTextEntry autoComplete="current-password" textContentType="password" />
        <Input label="New password" value={passwords.next} onChangeText={(v) => setPasswords((p) => ({ ...p, next: v }))} secureTextEntry autoComplete="new-password" textContentType="newPassword" hint="At least 8 characters with a letter and a number." />
        <Button title="Change password" variant="outline" loading={changePassword.isPending} disabled={!passwords.current || passwords.next.length < 8} onPress={() => changePassword.mutate()} />
      </Card>

      <Card style={{ borderColor: colors.danger + "55" }}>
        <Text variant="subheading" tone="danger">Delete account</Text>
        <Text variant="small" tone="muted">Permanently deletes your account, recordings and all learning data. This cannot be undone.</Text>
        <Notice tone="danger">Enter your password to confirm.</Notice>
        <Input value={deletePassword} onChangeText={setDeletePassword} secureTextEntry accessibilityLabel="Password to confirm deletion" autoComplete="current-password" />
        <View>
          <Button
            title="Delete my account"
            variant="danger"
            disabled={!deletePassword}
            loading={deleteAccount.isPending}
            onPress={() => confirmAction("Delete your account?", "All of your learning data will be permanently removed.", () => deleteAccount.mutate(), "Delete")}
          />
        </View>
      </Card>
    </Screen>
  );
}

export default function SettingsScreen() {
  const { data: me, isLoading } = useMe();
  if (isLoading || !me) return <Loading />;
  return <SettingsForm me={me} />;
}
