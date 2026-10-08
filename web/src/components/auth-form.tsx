"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button, Card, Field, Input, Notice } from "@/components/ui";
import { ApiError, fieldErrors, request } from "@/lib/api";
import type { User } from "@/lib/types";

/** Shared sign-in / registration form. Credentials go to the BFF, which stores the session in httpOnly cookies. */
export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    setFields({});
    try {
      const payload =
        mode === "login"
          ? { email: form.get("email"), password: form.get("password") }
          : { name: form.get("name"), email: form.get("email"), password: form.get("password") };
      const result = await request<{ user: User }>(`/api/auth/${mode}`, { json: payload });
      const next = params.get("next");
      const destination = !result.user.profile.onboarding_completed ? "/onboarding" : next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
      window.location.assign(destination);
    } catch (err) {
      setFields(fieldErrors(err));
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
      setBusy(false);
    }
  }

  return (
    <Card className="w-full max-w-md p-6 sm:p-8">
      <h1 className="text-2xl font-semibold tracking-tight">{mode === "login" ? "Welcome back" : "Create your account"}</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        {mode === "login" ? "Sign in to continue your learning plan." : "Free to start. Your plan adapts after a 15-minute diagnostic."}
      </p>
      <form className="mt-6 space-y-4" onSubmit={onSubmit} noValidate>
        {mode === "register" && (
          <Field label="Name" htmlFor="name" error={fields.name}>
            <Input id="name" name="name" autoComplete="name" required maxLength={100} invalid={!!fields.name} />
          </Field>
        )}
        <Field label="Email" htmlFor="email" error={fields.email}>
          <Input id="email" name="email" type="email" autoComplete="email" required invalid={!!fields.email} />
        </Field>
        <Field label="Password" htmlFor="password" error={fields.password} hint={mode === "register" ? "At least 8 characters, with a letter and a number." : undefined}>
          <Input id="password" name="password" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} required minLength={mode === "register" ? 8 : 1} invalid={!!fields.password} />
        </Field>
        {error && (
          <Notice tone="danger" className="text-sm">
            {error}
          </Notice>
        )}
        <Button type="submit" className="w-full" size="lg" loading={busy}>
          {mode === "login" ? "Sign in" : "Create account"}
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-muted-foreground">
        {mode === "login" ? (
          <>
            New to LinguaSI?{" "}
            <Link href="/register" className="font-medium text-primary hover:underline">
              Create an account
            </Link>
          </>
        ) : (
          <>
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-primary hover:underline">
              Sign in
            </Link>
          </>
        )}
      </p>
    </Card>
  );
}
