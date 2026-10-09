"use client";

import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { useToast } from "@/components/providers/toast";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button, Card, CardBody, CardHeader, Field, Input, Notice, PageHeader, PageSkeleton, Select } from "@/components/ui";
import { useMe, useUpdateProfile } from "@/hooks/use-me";
import { api, errorMessage, fieldErrors, request } from "@/lib/api";
import { leaveSession } from "@/lib/navigation";
import { BANDS, LEVELS, TOPICS } from "@/lib/constants";
import type { Profile, User } from "@/lib/types";
import { cn, titleCase } from "@/lib/utils";

export default function SettingsPage() {
  const { data: me, isLoading } = useMe();
  if (isLoading || !me) return <PageSkeleton />;
  return <SettingsForm me={me} />;
}

function SettingsForm({ me }: { me: User }) {
  const update = useUpdateProfile();
  const { push } = useToast();
  const [form, setForm] = useState<Partial<Profile> & { name?: string }>(() => ({ ...me.profile, name: me.name }));
  const [passwords, setPasswords] = useState({ current: "", next: "" });
  const [deletePassword, setDeletePassword] = useState("");

  const changePassword = useMutation({
    mutationFn: () => api("/me/change-password", { json: { current_password: passwords.current, new_password: passwords.next } }),
    onSuccess: () => {
      push({ tone: "success", title: "Password changed", description: "Other devices have been signed out." });
      setPasswords({ current: "", next: "" });
    },
    onError: (err) => push({ tone: "error", title: "Password not changed", description: Object.values(fieldErrors(err))[0] ?? errorMessage(err) }),
  });
  const deleteAccount = useMutation({
    mutationFn: () => api("/me/delete", { json: { password: deletePassword } }),
    onSuccess: async () => {
      await request("/api/auth/logout", { method: "POST" }).catch(() => undefined);
      leaveSession("/");
    },
    onError: (err) => push({ tone: "error", title: "Account not deleted", description: errorMessage(err) }),
  });

  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm((f) => ({ ...f, [key]: value }));

  function save(event: FormEvent) {
    event.preventDefault();
    const { name, goal, ielts_module, self_reported_level, target_band, test_date, daily_minutes, preferred_mode, confidence, preferred_topics, timezone, keep_recordings } = form;
    update.mutate(
      { name, goal, ielts_module, self_reported_level, target_band, daily_minutes, preferred_mode, confidence, preferred_topics, timezone, keep_recordings, ...(test_date ? { test_date } : { clear_test_date: true }) },
      {
        onSuccess: () => push({ tone: "success", title: "Settings saved", description: "Your plan and recommendations will adapt." }),
        onError: (err) => push({ tone: "error", title: "Settings not saved", description: errorMessage(err) }),
      },
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title="Settings" description={me.email} />
      <Card>
        <CardHeader title="Appearance" description="Choose light, dark, or follow your system. Saved to your account." />
        <CardBody>
          <ThemeToggle />
        </CardBody>
      </Card>

      <form onSubmit={save}>
        <Card>
          <CardHeader title="Learning profile" description="SI uses these to plan missions and choose content." />
          <CardBody className="grid gap-4 sm:grid-cols-2">
            <Field label="Name" htmlFor="name">
              <Input id="name" value={form.name ?? ""} onChange={(e) => set("name", e.target.value)} maxLength={100} />
            </Field>
            <Field label="Goal" htmlFor="goal">
              <Select id="goal" value={form.goal} onChange={(e) => set("goal", e.target.value as Profile["goal"])}>
                <option value="ielts">IELTS preparation</option>
                <option value="general">General English</option>
              </Select>
            </Field>
            {form.goal === "ielts" && (
              <>
                <Field label="IELTS module" htmlFor="module">
                  <Select id="module" value={form.ielts_module} onChange={(e) => set("ielts_module", e.target.value as Profile["ielts_module"])}>
                    <option value="academic">Academic</option>
                    <option value="general_training">General Training</option>
                  </Select>
                </Field>
                <Field label="Target band" htmlFor="target">
                  <Select id="target" value={form.target_band} onChange={(e) => set("target_band", Number(e.target.value))}>
                    {BANDS.map((b) => (
                      <option key={b} value={b}>
                        {b.toFixed(1)}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Test date" htmlFor="test-date" hint="Leave empty if you haven't booked yet.">
                  <Input id="test-date" type="date" value={form.test_date ?? ""} onChange={(e) => set("test_date", e.target.value || null)} />
                </Field>
              </>
            )}
            <Field label="Self-assessed level" htmlFor="level">
              <Select id="level" value={form.self_reported_level} onChange={(e) => set("self_reported_level", e.target.value)}>
                {LEVELS.map((l) => (
                  <option key={l.value} value={l.value}>
                    {l.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={`Daily study time: ${form.daily_minutes} min`} htmlFor="minutes">
              <input id="minutes" type="range" min={10} max={120} step={5} value={form.daily_minutes} onChange={(e) => set("daily_minutes", Number(e.target.value))} className="w-full accent-[var(--primary)]" />
            </Field>
            <Field label="Preferred style" htmlFor="mode">
              <Select id="mode" value={form.preferred_mode} onChange={(e) => set("preferred_mode", e.target.value as Profile["preferred_mode"])}>
                <option value="guided">Guided</option>
                <option value="balanced">Balanced</option>
                <option value="exam">Exam-like</option>
              </Select>
            </Field>
            <Field label="Time zone" htmlFor="tz" hint="Used for streaks and daily missions.">
              <Input id="tz" value={form.timezone ?? ""} onChange={(e) => set("timezone", e.target.value)} />
            </Field>
            <div className="space-y-2 sm:col-span-2">
              <p className="text-sm font-medium">Topics you enjoy</p>
              <div className="flex flex-wrap gap-2">
                {TOPICS.map((t) => {
                  const on = form.preferred_topics?.includes(t);
                  return (
                    <button
                      key={t}
                      type="button"
                      aria-pressed={on}
                      onClick={() => set("preferred_topics", on ? form.preferred_topics!.filter((x) => x !== t) : [...(form.preferred_topics ?? []), t])}
                      className={cn("rounded-full border px-3 py-1 text-sm", on ? "border-primary bg-primary-soft text-primary" : "border-border text-muted-foreground hover:bg-muted")}
                    >
                      {titleCase(t)}
                    </button>
                  );
                })}
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm sm:col-span-2">
              <input type="checkbox" checked={!!form.keep_recordings} onChange={(e) => set("keep_recordings", e.target.checked)} className="accent-[var(--primary)]" />
              Keep my speaking recordings so I can replay them (turn off to store transcripts only)
            </label>
            <div className="sm:col-span-2">
              <Button type="submit" loading={update.isPending}>
                Save changes
              </Button>
            </div>
          </CardBody>
        </Card>
      </form>

      <Card>
        <CardHeader title="Password" />
        <CardBody>
          <form
            className="grid gap-4 sm:grid-cols-2"
            onSubmit={(e) => {
              e.preventDefault();
              changePassword.mutate();
            }}
          >
            <Field label="Current password" htmlFor="current">
              <Input id="current" type="password" autoComplete="current-password" value={passwords.current} onChange={(e) => setPasswords((p) => ({ ...p, current: e.target.value }))} />
            </Field>
            <Field label="New password" htmlFor="new" hint="At least 8 characters with a letter and a number.">
              <Input id="new" type="password" autoComplete="new-password" value={passwords.next} onChange={(e) => setPasswords((p) => ({ ...p, next: e.target.value }))} />
            </Field>
            <div>
              <Button type="submit" variant="outline" loading={changePassword.isPending} disabled={!passwords.current || passwords.next.length < 8}>
                Change password
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>

      <Card className="border-danger/30">
        <CardHeader title="Delete account" description="Permanently deletes your account, recordings and all learning data. This cannot be undone." />
        <CardBody className="space-y-3">
          <Notice tone="danger">Enter your password to confirm.</Notice>
          <div className="flex flex-wrap gap-3">
            <Input type="password" value={deletePassword} onChange={(e) => setDeletePassword(e.target.value)} className="max-w-xs" aria-label="Password to confirm deletion" autoComplete="current-password" />
            <Button variant="danger" disabled={!deletePassword} loading={deleteAccount.isPending} onClick={() => deleteAccount.mutate()}>
              Delete my account
            </Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
