"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Send, Target } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useToast } from "@/components/providers/toast";
import { RichText } from "@/components/rich-text";
import { Badge, Button, ErrorState, Skeleton, Textarea } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { ActivityOutcome, Conversation, TutorMessage } from "@/lib/types";
import { cn } from "@/lib/utils";

const INTENT_LABELS: Record<string, string> = { sentence_check: "Sentence check", reveal: "Corrections", vocabulary: "Word help" };

/** Chat with the SI Tutor or a Lab role-play partner. */
export function Chat({ conversationId, suggestions = [] }: { conversationId: number; suggestions?: string[] }) {
  const queryClient = useQueryClient();
  const { push, celebrate } = useToast();
  const [draft, setDraft] = useState("");
  const bottom = useRef<HTMLDivElement>(null);
  const { data, error, isLoading, refetch } = useQuery({ queryKey: ["conversation", conversationId], queryFn: () => api<Conversation>(`/tutor/conversations/${conversationId}`) });

  const send = useMutation({
    mutationFn: (content: string) => api<{ user_message: TutorMessage; reply: TutorMessage; outcome: ActivityOutcome | null }>(`/tutor/conversations/${conversationId}/messages`, { json: { content } }),
    onMutate: () => setDraft(""),
    onSuccess: (res) => {
      queryClient.setQueryData<Conversation>(["conversation", conversationId], (c) => (c ? { ...c, messages: [...(c.messages ?? []), res.user_message, res.reply] } : c));
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      if (res.outcome) {
        celebrate(res.outcome);
        queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      }
    },
    onError: (err, content) => {
      setDraft(content);
      push({ tone: "error", title: "Message not sent", description: errorMessage(err) });
    },
  });

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [data?.messages?.length, send.isPending]);

  if (isLoading) return <Skeleton className="h-96" />;
  if (error || !data) return <ErrorState error={error} onRetry={() => refetch()} />;
  const scenario = data.scenario_info;

  return (
    <div className="flex h-[calc(100vh-11rem)] min-h-[480px] flex-col rounded-2xl border border-border bg-card">
      {scenario && (
        <div className="border-b border-border p-4 text-sm">
          <p className="flex items-center gap-2 font-semibold">
            <Target className="size-4 text-primary" aria-hidden /> {scenario.goal}
          </p>
          <p className="mt-1 text-muted-foreground">
            You&apos;re talking to {scenario.ai_role}. Useful phrases: {scenario.phrases.join(" · ")}
          </p>
        </div>
      )}
      <div className="flex-1 space-y-4 overflow-y-auto p-4" aria-live="polite">
        {(data.messages ?? []).map((m) => (
          <div key={m.id} className={cn("flex gap-3", m.role === "user" && "flex-row-reverse")}>
            {m.role === "assistant" && (
              <div className="grid size-8 shrink-0 place-items-center rounded-full bg-primary-soft text-primary">
                <Bot className="size-4" aria-hidden />
              </div>
            )}
            <div className={cn("max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed", m.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted")}>
              {m.role === "assistant" && typeof m.meta?.intent === "string" && INTENT_LABELS[m.meta.intent] && (
                <Badge tone="primary" className="mb-1.5">
                  {INTENT_LABELS[m.meta.intent]}
                </Badge>
              )}
              {m.role === "assistant" ? <RichText text={m.content} /> : <p className="whitespace-pre-wrap">{m.content}</p>}
            </div>
          </div>
        ))}
        {send.isPending && (
          <div className="flex gap-3">
            <div className="grid size-8 shrink-0 place-items-center rounded-full bg-primary-soft text-primary">
              <Bot className="size-4" aria-hidden />
            </div>
            <div className="rounded-2xl bg-muted px-4 py-2.5 text-sm text-muted-foreground">Thinking…</div>
          </div>
        )}
        <div ref={bottom} />
      </div>
      {suggestions.length > 0 && (data.messages?.length ?? 0) <= 1 && (
        <div className="flex flex-wrap gap-2 px-4 pb-2">
          {suggestions.map((s) => (
            <button key={s} onClick={() => setDraft(s)} className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground hover:bg-muted">
              {s}
            </button>
          ))}
        </div>
      )}
      <form
        className="flex items-end gap-2 border-t border-border p-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (draft.trim()) send.mutate(draft.trim());
        }}
      >
        <Textarea
          rows={2}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (draft.trim() && !send.isPending) send.mutate(draft.trim());
            }
          }}
          placeholder={scenario ? "Reply in English…" : 'Ask a question, or write "check: your sentence"'}
          aria-label="Message"
          maxLength={2000}
          className="resize-none"
        />
        <Button type="submit" disabled={!draft.trim()} loading={send.isPending} aria-label="Send message">
          <Send className="size-4" />
        </Button>
      </form>
    </div>
  );
}
