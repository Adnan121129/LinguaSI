"use client";

import { ArrowRight, BookOpen, ChevronLeft, GraduationCap, Languages } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useToast } from "@/components/providers/toast";
import { Button, Card, Field, Input, ProgressBar, Select } from "@/components/ui";
import { useMe } from "@/hooks/use-me";
import { api, errorMessage } from "@/lib/api";
import { BANDS, LEVELS, TOPICS } from "@/lib/constants";
import type { User } from "@/lib/types";
import { cn, titleCase } from "@/lib/utils";

/** Today's date as YYYY-MM-DD in the learner's own timezone (toISOString would give the UTC date). */
function localToday() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

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

function Choice({ selected, onClick, title, text, icon }: { selected: boolean; onClick: () => void; title: string; text: string; icon?: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={cn("flex w-full items-start gap-3 rounded-2xl border p-4 text-left transition", selected ? "border-primary bg-primary-soft" : "border-border hover:bg-muted")}
    >
      {icon && <span className="mt-0.5 text-primary">{icon}</span>}
      <span>
        <span className="block font-medium">{title}</span>
        <span className="block text-sm text-muted-foreground">{text}</span>
      </span>
    </button>
  );
}

export default function OnboardingPage() {
  const router = useRouter();
  const { push } = useToast();
  const { data: me } = useMe();
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
  const steps = ["Goal", "Level", "Routine"];

  async function finish(takeDiagnostic: boolean) {
    setSaving(true);
    try {
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      const user = await api<User>("/onboarding", {
        json: {
          ...form,
          test_date: form.goal === "ielts" && form.test_date ? form.test_date : null,
          timezone,
          name: me?.name,
        },
      });
      router.prefetch("/dashboard");
      push({ tone: "success", title: "Your learning plan is ready", description: takeDiagnostic ? "Let's measure your starting level." : undefined });
      if (user) window.location.assign(takeDiagnostic ? "/onboarding/diagnostic" : "/dashboard");
    } catch (err) {
      push({ tone: "error", title: "Couldn't save your preferences", description: errorMessage(err) });
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6">
        <p className="text-sm font-medium text-primary">Welcome{me ? `, ${me.name.split(" ")[0]}` : ""}</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">Let&apos;s personalise LinguaSI for you</h1>
        <div className="mt-4 flex items-center gap-3">
          <ProgressBar value={((step + 1) / steps.length) * 100} label="Onboarding progress" />
          <span className="shrink-0 text-xs text-muted-foreground">
            Step {step + 1} of {steps.length}
          </span>
        </div>
      </div>

      <Card className="p-6">
        {step === 0 && (
          <div className="space-y-5">
            <h2 className="font-semibold">What is your main goal?</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <Choice selected={form.goal === "ielts"} onClick={() => set("goal", "ielts")} title="Prepare for IELTS" text="IELTS-style practice with AI estimated bands." icon={<GraduationCap className="size-5" />} />
              <Choice selected={form.goal === "general"} onClick={() => set("goal", "general")} title="Improve my English" text="Everyday and work English with the English Lab." icon={<Languages className="size-5" />} />
            </div>
            {form.goal === "ielts" && (
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Module" htmlFor="module">
                  <Select id="module" value={form.ielts_module} onChange={(e) => set("ielts_module", e.target.value as Form["ielts_module"])}>
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
                <Field label="Test date (optional)" htmlFor="date">
                  <Input id="date" type="date" value={form.test_date} min={localToday()} onChange={(e) => set("test_date", e.target.value)} />
                </Field>
              </div>
            )}
          </div>
        )}

        {step === 1 && (
          <div className="space-y-5">
            <h2 className="font-semibold">How would you describe your English today?</h2>
            <div className="grid gap-2">
              {LEVELS.map((level) => (
                <Choice key={level.value} selected={form.self_reported_level === level.value} onClick={() => set("self_reported_level", level.value)} title={level.label} text={level.hint} />
              ))}
            </div>
            <Field label={`How confident do you feel speaking English? (${form.confidence}/5)`} htmlFor="confidence">
              <input id="confidence" type="range" min={1} max={5} value={form.confidence} onChange={(e) => set("confidence", Number(e.target.value))} className="w-full accent-[var(--primary)]" />
            </Field>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-5">
            <h2 className="font-semibold">Your study routine</h2>
            <Field label={`Daily study time: ${form.daily_minutes} minutes`} htmlFor="minutes" hint="Your daily mission is sized to fit this.">
              <input id="minutes" type="range" min={10} max={120} step={5} value={form.daily_minutes} onChange={(e) => set("daily_minutes", Number(e.target.value))} className="w-full accent-[var(--primary)]" />
            </Field>
            <div className="space-y-2">
              <p className="text-sm font-medium">Preferred style</p>
              <div className="grid gap-2 sm:grid-cols-3">
                {(
                  [
                    ["guided", "Guided", "More hints and explanations"],
                    ["balanced", "Balanced", "A mix of help and challenge"],
                    ["exam", "Exam-like", "Timed, realistic conditions"],
                  ] as const
                ).map(([value, title, text]) => (
                  <Choice key={value} selected={form.preferred_mode === value} onClick={() => set("preferred_mode", value)} title={title} text={text} />
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium">Topics you enjoy</p>
              <div className="flex flex-wrap gap-2">
                {TOPICS.map((topic) => {
                  const on = form.preferred_topics.includes(topic);
                  return (
                    <button
                      key={topic}
                      type="button"
                      aria-pressed={on}
                      onClick={() => set("preferred_topics", on ? form.preferred_topics.filter((t) => t !== topic) : [...form.preferred_topics, topic].slice(0, 12))}
                      className={cn("rounded-full border px-3 py-1 text-sm", on ? "border-primary bg-primary-soft text-primary" : "border-border text-muted-foreground hover:bg-muted")}
                    >
                      {titleCase(topic)}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
          <Button variant="ghost" onClick={() => setStep((s) => s - 1)} disabled={step === 0 || saving}>
            <ChevronLeft className="size-4" /> Back
          </Button>
          {step < steps.length - 1 ? (
            <Button onClick={() => setStep((s) => s + 1)}>
              Continue <ArrowRight className="size-4" />
            </Button>
          ) : (
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => finish(false)} disabled={saving}>
                Skip the diagnostic for now
              </Button>
              <Button onClick={() => finish(true)} loading={saving}>
                <BookOpen className="size-4" /> Take the 15-minute diagnostic
              </Button>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
