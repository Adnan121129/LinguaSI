"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, Eye, EyeOff, Plus, RefreshCw, Search, ShieldAlert } from "lucide-react";
import { useState, type FormEvent } from "react";

import { ChartCard, ColumnChart, shortDay } from "@/components/charts";
import { useToast } from "@/components/providers/toast";
import { Badge, Button, Card, CardBody, CardHeader, EmptyState, ErrorState, Field, Input, PageHeader, PageSkeleton, Select, Skeleton, Stat, Tabs, Textarea } from "@/components/ui";
import { useMe } from "@/hooks/use-me";
import { api, errorMessage, fieldErrors } from "@/lib/api";
import type { Page } from "@/lib/types";
import { formatDateTime, formatDuration, relativeTime, titleCase } from "@/lib/utils";

type Overview = {
  users: Record<string, number>;
  activity_7d: Record<string, number>;
  ai_24h: { calls: number; failures: number; mock_calls: number; avg_latency_ms: number | null; input_tokens: number; output_tokens: number };
  ai_config: Record<string, string | number | boolean>;
  content: Record<string, { total: number; hidden: number; ai_generated?: number }>;
  errors_24h: number;
};
type AdminUser = {
  id: number;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  is_demo: boolean;
  created_at: string;
  last_active_at: string | null;
  goal: string | null;
  estimated_cefr: string | null;
  estimated_band: number | null;
  total_xp: number;
  level: number;
};
type AdminUserDetail = AdminUser & {
  profile: { ielts_module: string | null; target_band: number | null; test_date: string | null; daily_minutes: number; timezone: string; weak_areas: { label: string; reason?: string }[]; strong_areas: { label: string; reason?: string }[] };
  totals: { study_minutes: number; writing_submissions: number; speaking_sessions: number; mistakes: Record<string, number>; vocabulary: Record<string, number> };
  recent_sessions: { activity: string; title: string; started_at: string; duration_seconds: number; score: number | null; xp: number }[];
  ai_usage: { task: string; calls: number; failures: number }[];
};
type ContentRow = { id: number; kind: string; title: string; subtitle: string; detail: unknown; difficulty: number; is_active: boolean; source: string; created_at: string };
type ContentDetail = { summary: ContentRow; data: Record<string, unknown>; editable_fields: string[] };
type Usage = {
  config: Record<string, unknown>;
  p95_latency_ms: number | null;
  by_task: { task: string; tier: string; calls: number; failures: number; avg_latency_ms: number | null; input_tokens: number; output_tokens: number }[];
  by_model: { provider: string; model: string; is_mock: boolean; calls: number; input_tokens: number; output_tokens: number }[];
  errors: { category: string; count: number }[];
  daily: { day: string; calls: number; failures: number; input_tokens: number; output_tokens: number }[];
  recent_failures: { id: number; task: string; provider: string; model: string; error_category: string; error_message: string; attempts: number; created_at: string }[];
};

const PAGE_SIZE = 50;

function query(params: Record<string, string | number | undefined>) {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) if (value !== undefined && value !== "") qs.set(key, String(value));
  return qs.toString();
}

/** "Showing 51-100 of 195" with previous / next buttons; renders nothing when everything fits on one page. */
function Pager({ page, total, onPage }: { page: number; total: number; onPage: (page: number) => void }) {
  if (total <= PAGE_SIZE) return null;
  const last = Math.ceil(total / PAGE_SIZE);
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-3 text-sm">
      <p className="text-muted-foreground">
        Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(total, page * PAGE_SIZE)} of {total}
      </p>
      <div className="flex gap-2">
        <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Previous
        </Button>
        <Button size="sm" variant="outline" disabled={page >= last} onClick={() => onPage(page + 1)}>
          Next
        </Button>
      </div>
    </div>
  );
}

function SearchBox({ label, placeholder, onSearch, className }: { label: string; placeholder: string; onSearch: (q: string) => void; className?: string }) {
  const [q, setQ] = useState("");
  return (
    <form
      className={className ?? "flex gap-2"}
      onSubmit={(e) => {
        e.preventDefault();
        onSearch(q.trim());
      }}
    >
      <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={placeholder} aria-label={label} />
      <Button type="submit" variant="secondary" aria-label="Search">
        <Search className="size-4" />
      </Button>
    </form>
  );
}

function OverviewTab() {
  const { data, error, isLoading, refetch } = useQuery({ queryKey: ["admin-overview"], queryFn: () => api<Overview>("/admin/overview") });
  if (isLoading) return <Skeleton className="h-64" />;
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />;
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader title="Users" />
          <CardBody className="grid grid-cols-2 gap-3">
            {Object.entries(data.users).map(([k, v]) => (
              <Stat key={k} label={titleCase(k)} value={v} />
            ))}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="AI (last 24 hours)" description={`${data.ai_config.effective_provider} · ${data.ai_config.mock_mode ? "Mock AI Mode" : "live provider"}`} />
          <CardBody className="grid grid-cols-2 gap-3">
            <Stat label="Calls" value={data.ai_24h.calls} />
            <Stat label="Failures" value={data.ai_24h.failures} />
            <Stat label="Avg latency" value={data.ai_24h.avg_latency_ms === null ? "—" : `${data.ai_24h.avg_latency_ms} ms`} />
            <Stat label="Tokens" value={(data.ai_24h.input_tokens + data.ai_24h.output_tokens).toLocaleString()} />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Errors (24h)" />
          <CardBody>
            <Stat label="Error logs" value={data.errors_24h} icon={<ShieldAlert className="size-4" />} />
            <div className="mt-4 space-y-1 text-xs text-muted-foreground">
              <p>Fast model: {String(data.ai_config.model_fast)}</p>
              <p>Strong model: {String(data.ai_config.model_strong)}</p>
              <p>
                Speech: STT {String(data.ai_config.stt_provider)} · TTS {String(data.ai_config.tts_provider)}
              </p>
            </div>
          </CardBody>
        </Card>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader title="Learning activity (7 days)" />
          <CardBody className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {Object.entries(data.activity_7d).map(([k, v]) => (
              <Stat key={k} label={titleCase(k)} value={v} />
            ))}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Content" />
          <CardBody>
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="py-1">Type</th>
                  <th>Total</th>
                  <th>Hidden</th>
                  <th>AI-generated</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.content).map(([k, v]) => (
                  <tr key={k} className="border-t border-border">
                    <td className="py-1.5">{titleCase(k)}</td>
                    <td>{v.total}</td>
                    <td>{v.hidden}</td>
                    <td>{v.ai_generated ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function UserDetail({ id, isSelf, onClose }: { id: number; isSelf: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const { push } = useToast();
  const detail = useQuery({ queryKey: ["admin-user", id], queryFn: () => api<AdminUserDetail>(`/admin/users/${id}`) });
  const update = useMutation({
    mutationFn: (body: { is_active?: boolean; role?: string }) => api<AdminUser>(`/admin/users/${id}`, { method: "PATCH", json: body }),
    onSuccess: (user) => {
      push({ tone: "success", title: "User updated", description: `${user.email} is ${user.is_active ? "active" : "deactivated"} · ${user.role}` });
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      queryClient.invalidateQueries({ queryKey: ["admin-user", id] });
      queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
    },
    onError: (err) => push({ tone: "error", title: "User not updated", description: errorMessage(err) }),
  });
  if (detail.isLoading) return <Skeleton className="h-48" />;
  if (detail.error || !detail.data) return <ErrorState error={detail.error} onRetry={() => detail.refetch()} />;
  const u = detail.data;
  function change(body: { is_active?: boolean; role?: string }, question: string) {
    if (window.confirm(question)) update.mutate(body);
  }
  return (
    <Card className="border-primary/30">
      <CardHeader
        title={u.name}
        description={`${u.email} · joined ${formatDateTime(u.created_at)}`}
        action={
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        }
      />
      <CardBody className="space-y-5">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Level" value={`L${u.level} · ${u.total_xp.toLocaleString()} XP`} />
          <Stat label="Estimate" value={u.estimated_band !== null ? `Band ${u.estimated_band}` : u.estimated_cefr ?? "—"} />
          <Stat label="Study time" value={`${u.totals.study_minutes} min`} />
          <Stat label="Target" value={u.profile.target_band ? `Band ${u.profile.target_band}` : titleCase(u.goal ?? "—")} />
          <Stat label="Essays" value={u.totals.writing_submissions} />
          <Stat label="Speaking tests" value={u.totals.speaking_sessions} />
          <Stat label="Open mistakes" value={u.totals.mistakes.unresolved ?? 0} />
          <Stat label="Words known" value={`${u.totals.vocabulary.known ?? 0} / ${u.totals.vocabulary.total ?? 0}`} />
        </div>
        {(u.profile.weak_areas.length > 0 || u.profile.strong_areas.length > 0) && (
          <div className="grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <p className="font-medium">Focus areas</p>
              <ul className="mt-1 list-disc pl-5 text-muted-foreground">
                {u.profile.weak_areas.map((w) => (
                  <li key={w.label}>{w.label}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="font-medium">Strengths</p>
              <ul className="mt-1 list-disc pl-5 text-muted-foreground">
                {u.profile.strong_areas.length ? u.profile.strong_areas.map((w) => <li key={w.label}>{w.label}</li>) : <li>None identified yet</li>}
              </ul>
            </div>
          </div>
        )}
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <p className="text-sm font-medium">Recent sessions</p>
            {u.recent_sessions.length ? (
              <ul className="mt-2 space-y-1 text-sm">
                {u.recent_sessions.map((s, i) => (
                  <li key={i} className="flex justify-between gap-3">
                    <span className="truncate">
                      <span className="text-muted-foreground">{titleCase(s.activity)}:</span> {s.title}
                    </span>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {formatDuration(s.duration_seconds)} · {relativeTime(s.started_at)}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">No sessions yet.</p>
            )}
          </div>
          <div>
            <p className="text-sm font-medium">AI calls by task</p>
            {u.ai_usage.length ? (
              <ul className="mt-2 space-y-1 text-sm">
                {u.ai_usage.map((a) => (
                  <li key={a.task} className="flex justify-between">
                    <span>{a.task}</span>
                    <span className="text-muted-foreground">
                      {a.calls} {a.calls === 1 ? "call" : "calls"}
                      {a.failures ? ` · ${a.failures} failed` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">No AI calls.</p>
            )}
          </div>
        </div>
        {isSelf ? (
          <p className="text-xs text-muted-foreground">This is your account. Another admin must change your role or status.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant={u.is_active ? "outline" : "secondary"}
              loading={update.isPending}
              onClick={() =>
                change({ is_active: !u.is_active }, u.is_active ? `Deactivate ${u.email}? They will be signed out on every device.` : `Reactivate ${u.email}?`)
              }
            >
              {u.is_active ? "Deactivate" : "Reactivate"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              loading={update.isPending}
              onClick={() =>
                change({ role: u.role === "admin" ? "learner" : "admin" }, u.role === "admin" ? `Remove admin access from ${u.email}?` : `Give ${u.email} full admin access?`)
              }
            >
              {u.role === "admin" ? "Remove admin role" : "Make admin"}
            </Button>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function UsersTab() {
  const { data: me } = useMe();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number | null>(null);
  const users = useQuery({
    queryKey: ["admin-users", search, page],
    queryFn: () => api<Page<AdminUser>>(`/admin/users?${query({ q: search, page, page_size: PAGE_SIZE })}`),
    placeholderData: keepPreviousData,
  });
  return (
    <div className="space-y-4">
      {selected !== null && <UserDetail key={selected} id={selected} isSelf={selected === me?.id} onClose={() => setSelected(null)} />}
      <Card>
        <SearchBox
          className="flex gap-2 border-b border-border p-4"
          label="Search users"
          placeholder="Search by name or email"
          onSearch={(q) => {
            setSearch(q);
            setPage(1);
          }}
        />
        {users.isLoading ? (
          <div className="p-4">
            <Skeleton className="h-40" />
          </div>
        ) : users.error ? (
          <div className="p-4">
            <ErrorState error={users.error} onRetry={() => users.refetch()} />
          </div>
        ) : users.data?.items.length ? (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted text-left text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2">User</th>
                    <th className="px-4 py-2">Level</th>
                    <th className="px-4 py-2">Estimate</th>
                    <th className="px-4 py-2">Last active</th>
                    <th className="px-4 py-2">Status</th>
                    <th className="px-4 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {users.data.items.map((u) => (
                    <tr key={u.id} className="border-t border-border">
                      <td className="px-4 py-2">
                        <p className="font-medium">
                          {u.name} {u.role === "admin" && <Badge tone="primary">admin</Badge>} {u.is_demo && <Badge tone="accent">demo</Badge>}
                        </p>
                        <p className="text-xs text-muted-foreground">{u.email}</p>
                      </td>
                      <td className="px-4 py-2">
                        L{u.level} · {u.total_xp.toLocaleString()} XP
                      </td>
                      <td className="px-4 py-2">{u.estimated_band !== null ? `${u.estimated_band} · ${u.estimated_cefr}` : u.estimated_cefr ?? "—"}</td>
                      <td className="px-4 py-2 text-muted-foreground">{u.last_active_at ? relativeTime(u.last_active_at) : "never"}</td>
                      <td className="px-4 py-2">{u.is_active ? <Badge tone="success">active</Badge> : <Badge tone="danger">deactivated</Badge>}</td>
                      <td className="px-4 py-2 text-right">
                        <Button size="sm" variant="ghost" onClick={() => setSelected(u.id)} aria-label={`Open ${u.email}`}>
                          Details
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={page} total={users.data.total} onPage={setPage} />
          </>
        ) : (
          <EmptyState title="No users match" />
        )}
      </Card>
    </div>
  );
}

function ContentEditor({ kind, id, onClose }: { kind: string; id: number; onClose: () => void }) {
  const queryClient = useQueryClient();
  const { push } = useToast();
  const detail = useQuery({ queryKey: ["admin-content-item", kind, id], queryFn: () => api<ContentDetail>(`/admin/content/${kind}/${id}`) });
  const [draft, setDraft] = useState<Record<string, string>>({});
  const save = useMutation({
    mutationFn: (changes: Record<string, unknown>) => api<ContentDetail>(`/admin/content/${kind}/${id}`, { method: "PATCH", json: changes }),
    onSuccess: () => {
      push({ tone: "success", title: "Saved" });
      setDraft({});
      queryClient.invalidateQueries({ queryKey: ["admin-content"] });
      queryClient.invalidateQueries({ queryKey: ["admin-content-item", kind, id] });
    },
    onError: (err) => push({ tone: "error", title: "Not saved", description: errorMessage(err) }),
  });
  if (detail.isLoading) return <Skeleton className="h-40" />;
  if (detail.error || !detail.data) return <ErrorState error={detail.error} />;
  const fields = detail.data.editable_fields.filter((f) => f !== "is_active");
  function submit() {
    const changes: Record<string, unknown> = {};
    for (const [field, raw] of Object.entries(draft)) {
      const original = detail.data!.data[field];
      if (Array.isArray(original)) changes[field] = raw.split("\n").map((s) => s.trim()).filter(Boolean);
      else if (typeof original === "number") changes[field] = Number(raw);
      else changes[field] = raw;
    }
    save.mutate(changes);
  }
  return (
    <Card className="border-primary/30">
      <CardHeader title={`Edit ${kind} #${id}`} description="Edits to curated items are kept when the seed command runs again." action={<Button variant="ghost" size="sm" onClick={onClose}>Close</Button>} />
      <CardBody className="space-y-3">
        {fields.map((field) => {
          const value = detail.data!.data[field];
          const text = draft[field] ?? (Array.isArray(value) ? value.join("\n") : value === null || value === undefined ? "" : String(value));
          return (
            <label key={field} className="block space-y-1 text-sm">
              <span className="font-medium">
                {titleCase(field)} {Array.isArray(value) && <span className="text-xs text-muted-foreground">(one per line)</span>}
              </span>
              {typeof value === "number" ? (
                <Input type="number" value={text} onChange={(e) => setDraft((d) => ({ ...d, [field]: e.target.value }))} />
              ) : (
                <Textarea rows={Array.isArray(value) || text.length > 80 ? 3 : 1} value={text} onChange={(e) => setDraft((d) => ({ ...d, [field]: e.target.value }))} />
              )}
            </label>
          );
        })}
        <Button onClick={submit} disabled={!Object.keys(draft).length} loading={save.isPending}>
          Save changes
        </Button>
      </CardBody>
    </Card>
  );
}

const PARTS_OF_SPEECH = ["noun", "verb", "adjective", "adverb", "phrase", "phrasal verb", "preposition", "conjunction", "idiom", "collocation"];
const CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];

function AddWordForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient();
  const { push } = useToast();
  const [form, setForm] = useState({ word: "", part_of_speech: "noun", definition: "", example: "", synonyms: "", collocations: "", topics: "", cefr: "B2", is_academic: false });
  const list = (value: string) => value.split(",").map((v) => v.trim()).filter(Boolean).slice(0, 10);
  const create = useMutation({
    mutationFn: () => api<ContentDetail>("/admin/content/vocabulary", { json: { ...form, synonyms: list(form.synonyms), collocations: list(form.collocations), topics: list(form.topics) } }),
    onSuccess: () => {
      push({ tone: "success", title: `"${form.word.trim()}" added`, description: "Learners can now meet it in vocabulary sessions." });
      queryClient.invalidateQueries({ queryKey: ["admin-content"] });
      queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
      onDone();
    },
  });
  const errors = create.error ? fieldErrors(create.error) : {};
  const set = (key: keyof typeof form, value: string | boolean) => setForm((f) => ({ ...f, [key]: value }));
  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate();
  }
  return (
    <Card className="border-primary/30">
      <CardHeader
        title="Add a word"
        description="Write an original definition and example sentence. New words join the adaptive vocabulary bank immediately."
        action={
          <Button variant="ghost" size="sm" onClick={onDone}>
            Cancel
          </Button>
        }
      />
      <CardBody>
        <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
          <Field label="Word or phrase" htmlFor="new-word" error={errors.word}>
            <Input id="new-word" value={form.word} onChange={(e) => set("word", e.target.value)} maxLength={80} required />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Part of speech" htmlFor="new-pos" error={errors.part_of_speech}>
              <Select id="new-pos" value={form.part_of_speech} onChange={(e) => set("part_of_speech", e.target.value)}>
                {PARTS_OF_SPEECH.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="CEFR level" htmlFor="new-cefr" error={errors.cefr}>
              <Select id="new-cefr" value={form.cefr} onChange={(e) => set("cefr", e.target.value)}>
                {CEFR_LEVELS.map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <Field label="Definition" htmlFor="new-def" error={errors.definition}>
            <Textarea id="new-def" rows={2} value={form.definition} onChange={(e) => set("definition", e.target.value)} maxLength={500} required />
          </Field>
          <Field label="Example sentence" htmlFor="new-example" error={errors.example}>
            <Textarea id="new-example" rows={2} value={form.example} onChange={(e) => set("example", e.target.value)} maxLength={500} required />
          </Field>
          <Field label="Synonyms" htmlFor="new-syn" hint="Comma-separated, up to 10." error={errors.synonyms}>
            <Input id="new-syn" value={form.synonyms} onChange={(e) => set("synonyms", e.target.value)} />
          </Field>
          <Field label="Collocations" htmlFor="new-col" hint="Comma-separated, e.g. pose a threat, a growing threat." error={errors.collocations}>
            <Input id="new-col" value={form.collocations} onChange={(e) => set("collocations", e.target.value)} />
          </Field>
          <Field label="Topics" htmlFor="new-topics" hint="Comma-separated, e.g. environment, technology." error={errors.topics}>
            <Input id="new-topics" value={form.topics} onChange={(e) => set("topics", e.target.value)} />
          </Field>
          <label className="flex items-center gap-2 self-end pb-2 text-sm">
            <input type="checkbox" checked={form.is_academic} onChange={(e) => set("is_academic", e.target.checked)} className="size-4 accent-[var(--primary)]" />
            Academic word (useful for IELTS Writing)
          </label>
          {create.error && !Object.keys(errors).length && <p className="text-sm text-danger sm:col-span-2">{errorMessage(create.error)}</p>}
          <div className="sm:col-span-2">
            <Button type="submit" loading={create.isPending}>
              Add word
            </Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}

function ContentTab() {
  const queryClient = useQueryClient();
  const { push } = useToast();
  const [kind, setKind] = useState("vocabulary");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);
  const content = useQuery({
    queryKey: ["admin-content", kind, search, page],
    queryFn: () => api<Page<ContentRow>>(`/admin/content/${kind}?${query({ q: search, page, page_size: PAGE_SIZE })}`),
    placeholderData: keepPreviousData,
  });
  const toggle = useMutation({
    mutationFn: (row: ContentRow) => api(`/admin/content/${kind}/${row.id}`, { method: "PATCH", json: { is_active: !row.is_active } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-content"] }),
    onError: (err) => push({ tone: "error", title: "Not updated", description: errorMessage(err) }),
  });
  const seed = useMutation({
    mutationFn: () => api<{ loaded: Record<string, number> }>("/admin/seed", { method: "POST" }),
    onSuccess: (res) => {
      push({ tone: "success", title: "Seed content reloaded", description: Object.entries(res.loaded).map(([k, v]) => `${v} ${k}`).join(", ") });
      queryClient.invalidateQueries({ queryKey: ["admin-content"] });
    },
    onError: (err) => push({ tone: "error", title: "Seed content not reloaded", description: errorMessage(err) }),
  });
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Select
          aria-label="Content type"
          value={kind}
          onChange={(e) => {
            setKind(e.target.value);
            setEditing(null);
            setAdding(false);
            setPage(1);
          }}
          className="w-auto"
        >
          {["vocabulary", "grammar", "reading", "listening", "writing", "speaking"].map((k) => (
            <option key={k} value={k}>
              {titleCase(k)}
            </option>
          ))}
        </Select>
        <SearchBox
          className="flex flex-1 gap-2"
          label="Search content"
          placeholder="Search"
          onSearch={(q) => {
            setSearch(q);
            setPage(1);
          }}
        />
        {kind === "vocabulary" && (
          <Button variant="secondary" onClick={() => (setAdding(true), setEditing(null))}>
            <Plus className="size-4" /> Add word
          </Button>
        )}
        <Button variant="outline" onClick={() => seed.mutate()} loading={seed.isPending}>
          <RefreshCw className="size-4" /> Reload seed content
        </Button>
      </div>
      {adding && kind === "vocabulary" && <AddWordForm onDone={() => setAdding(false)} />}
      {editing && <ContentEditor key={`${kind}-${editing}`} kind={kind} id={editing} onClose={() => setEditing(null)} />}
      {content.isLoading ? (
        <Skeleton className="h-60" />
      ) : content.error ? (
        <ErrorState error={content.error} onRetry={() => content.refetch()} />
      ) : content.data?.items.length ? (
        <Card>
          <ul className="divide-y divide-border">
            {content.data.items.map((row) => (
              <li key={row.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="font-medium">
                    {row.title} {!row.is_active && <Badge tone="danger">hidden</Badge>} <Badge>{row.source}</Badge>
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {row.subtitle} · difficulty {row.difficulty}
                  </p>
                </div>
                <Button size="sm" variant="ghost" onClick={() => (setEditing(row.id), setAdding(false))}>
                  Edit
                </Button>
                <Button size="sm" variant="outline" onClick={() => toggle.mutate(row)} aria-label={row.is_active ? `Hide ${row.title}` : `Show ${row.title}`}>
                  {row.is_active ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />} {row.is_active ? "Hide" : "Show"}
                </Button>
              </li>
            ))}
          </ul>
          <Pager page={page} total={content.data.total} onPage={setPage} />
        </Card>
      ) : (
        <EmptyState icon={<Database className="size-5" />} title="No content found" />
      )}
    </div>
  );
}

function EvaluationsTab() {
  const [kind, setKind] = useState<"writing" | "speaking">("writing");
  const [page, setPage] = useState(1);
  const evals = useQuery({
    queryKey: ["admin-evals", kind, page],
    queryFn: () =>
      api<Page<{ id: number; user_email: string; title: string; overall_band: number; criteria: Record<string, number | null>; provider: string; model: string; is_mock: boolean; error_count: number; created_at: string }>>(
        `/admin/evaluations?${query({ kind, page, page_size: PAGE_SIZE })}`,
      ),
    placeholderData: keepPreviousData,
  });
  return (
    <div className="space-y-4">
      <Tabs
        value={kind}
        onChange={(value) => {
          setKind(value);
          setPage(1);
        }}
        items={[
          { value: "writing", label: "Writing" },
          { value: "speaking", label: "Speaking" },
        ]}
      />
      {evals.isLoading ? (
        <Skeleton className="h-60" />
      ) : evals.error ? (
        <ErrorState error={evals.error} />
      ) : !evals.data?.items.length ? (
        <EmptyState title={`No ${kind} evaluations yet`} />
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-2">When</th>
                <th className="px-4 py-2">Learner</th>
                <th className="px-4 py-2">Task</th>
                <th className="px-4 py-2">Band</th>
                <th className="px-4 py-2">Criteria</th>
                <th className="px-4 py-2">Errors</th>
                <th className="px-4 py-2">Model</th>
              </tr>
            </thead>
            <tbody>
              {evals.data.items.map((e) => (
                <tr key={e.id} className="border-t border-border">
                  <td className="whitespace-nowrap px-4 py-2 text-muted-foreground">{formatDateTime(e.created_at)}</td>
                  <td className="px-4 py-2">{e.user_email}</td>
                  <td className="px-4 py-2">{e.title}</td>
                  <td className="px-4 py-2 font-semibold">{e.overall_band}</td>
                  <td className="px-4 py-2 text-xs text-muted-foreground">
                    {Object.entries(e.criteria)
                      .map(([k, v]) => `${k.split("_").map((w) => w[0]?.toUpperCase()).join("")} ${v ?? "—"}`)
                      .join(" · ")}
                  </td>
                  <td className="px-4 py-2">{e.error_count}</td>
                  <td className="px-4 py-2 text-xs">{e.is_mock ? "mock" : `${e.provider}/${e.model}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pager page={page} total={evals.data.total} onPage={setPage} />
        </Card>
      )}
    </div>
  );
}

function UsageTab() {
  const [days, setDays] = useState<"1" | "7" | "30">("7");
  const usage = useQuery({ queryKey: ["admin-usage", days], queryFn: () => api<Usage>(`/admin/ai-usage?days=${days}`) });
  if (usage.isLoading) return <Skeleton className="h-60" />;
  if (usage.error || !usage.data) return <ErrorState error={usage.error} />;
  const u = usage.data;
  return (
    <div className="space-y-6">
      <Tabs
        value={days}
        onChange={setDays}
        items={[
          { value: "1", label: "24 hours" },
          { value: "7", label: "7 days" },
          { value: "30", label: "30 days" },
        ]}
      />
      <ChartCard
        question="How much AI are we using each day?"
        description={`AI calls per day · p95 latency ${u.p95_latency_ms ?? "—"} ms`}
        rows={u.daily}
        columns={[
          { key: "day", label: "Day" },
          { key: "calls", label: "Calls" },
          { key: "failures", label: "Failures" },
          { key: "input_tokens", label: "Input tokens" },
          { key: "output_tokens", label: "Output tokens" },
        ]}
      >
        <ColumnChart data={u.daily} xKey="day" yKey="calls" label="Calls" xFormat={shortDay} />
      </ChartCard>
      <Card className="overflow-x-auto">
        <CardHeader title="By task" description="Model tier per task controls cost: fast models for short tasks, strong models for evaluations and generation." />
        <table className="mt-3 w-full text-sm">
          <thead className="bg-muted text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-2">Task</th>
              <th className="px-4 py-2">Tier</th>
              <th className="px-4 py-2">Calls</th>
              <th className="px-4 py-2">Failures</th>
              <th className="px-4 py-2">Avg latency</th>
              <th className="px-4 py-2">Tokens in / out</th>
            </tr>
          </thead>
          <tbody>
            {u.by_task.map((t) => (
              <tr key={`${t.task}-${t.tier}`} className="border-t border-border">
                <td className="px-4 py-2">{t.task}</td>
                <td className="px-4 py-2">
                  <Badge tone={t.tier === "strong" ? "primary" : "default"}>{t.tier}</Badge>
                </td>
                <td className="px-4 py-2">{t.calls}</td>
                <td className="px-4 py-2">{t.failures}</td>
                <td className="px-4 py-2">{t.avg_latency_ms ?? "—"} ms</td>
                <td className="px-4 py-2">
                  {t.input_tokens.toLocaleString()} / {t.output_tokens.toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      {u.recent_failures.length > 0 && (
        <Card>
          <CardHeader title="Recent failures" />
          <CardBody>
            <ul className="space-y-2 text-sm">
              {u.recent_failures.map((f) => (
                <li key={f.id}>
                  <Badge tone="danger">{f.error_category}</Badge> {f.task} · {f.provider}/{f.model} · {f.attempts} attempt(s) · {relativeTime(f.created_at)}
                  <p className="text-xs text-muted-foreground">{f.error_message}</p>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      )}
    </div>
  );
}

function LogsTab() {
  const [level, setLevel] = useState("");
  const [page, setPage] = useState(1);
  const logs = useQuery({
    queryKey: ["admin-logs", level, page],
    queryFn: () => api<Page<{ id: number; level: string; source: string; message: string; context: Record<string, unknown>; created_at: string }>>(`/admin/logs?${query({ level, page, page_size: PAGE_SIZE })}`),
    placeholderData: keepPreviousData,
  });
  return (
    <div className="space-y-4">
      <Select
        aria-label="Log level"
        value={level}
        onChange={(e) => {
          setLevel(e.target.value);
          setPage(1);
        }}
        className="w-auto"
      >
        <option value="">All levels</option>
        {["info", "warning", "error", "critical"].map((l) => (
          <option key={l} value={l}>
            {titleCase(l)}
          </option>
        ))}
      </Select>
      {logs.isLoading ? (
        <Skeleton className="h-60" />
      ) : logs.error ? (
        <ErrorState error={logs.error} />
      ) : logs.data?.items.length ? (
        <Card>
          <ul className="divide-y divide-border font-mono text-xs">
            {logs.data.items.map((l) => (
              <li key={l.id} className="flex flex-wrap gap-3 px-4 py-2">
                <span className="text-muted-foreground">{formatDateTime(l.created_at)}</span>
                <Badge tone={l.level === "error" || l.level === "critical" ? "danger" : l.level === "warning" ? "warning" : "default"}>{l.level}</Badge>
                <span className="text-muted-foreground">{l.source}</span>
                <span className="min-w-0 flex-1">{l.message}</span>
              </li>
            ))}
          </ul>
          <Pager page={page} total={logs.data.total} onPage={setPage} />
        </Card>
      ) : (
        <EmptyState title="No log entries" />
      )}
    </div>
  );
}

export default function AdminPage() {
  const { data: me, isLoading } = useMe();
  const [tab, setTab] = useState<"overview" | "users" | "content" | "evaluations" | "usage" | "logs">("overview");
  if (isLoading) return <PageSkeleton />;
  if (me?.role !== "admin") return <ErrorState title="Admins only" error={new Error("This area is available to administrators.")} />;
  return (
    <div className="space-y-6">
      <PageHeader title="Admin panel" description="Platform health, users, content quality and AI usage. Learner essays and transcripts are not shown here." />
      <div className="overflow-x-auto">
        <Tabs
          value={tab}
          onChange={setTab}
          items={[
            { value: "overview", label: "Overview" },
            { value: "users", label: "Users" },
            { value: "content", label: "Content" },
            { value: "evaluations", label: "Evaluations" },
            { value: "usage", label: "AI usage" },
            { value: "logs", label: "Logs" },
          ]}
        />
      </div>
      {tab === "overview" && <OverviewTab />}
      {tab === "users" && <UsersTab />}
      {tab === "content" && <ContentTab />}
      {tab === "evaluations" && <EvaluationsTab />}
      {tab === "usage" && <UsageTab />}
      {tab === "logs" && <LogsTab />}
    </div>
  );
}
