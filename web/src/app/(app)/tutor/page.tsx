"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageCircle, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Chat } from "@/components/chat";
import { useToast } from "@/components/providers/toast";
import { Button, Card, EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { Conversation, Page } from "@/lib/types";
import { cn, relativeTime } from "@/lib/utils";

const SUGGESTIONS = ["check: Yesterday I go to the library and borrow three books.", 'What does "mitigate" mean?', "What should I focus on this week?", "Explain the present perfect"];

export default function TutorPage() {
  const queryClient = useQueryClient();
  const { push } = useToast();
  const [active, setActive] = useState<number | null>(null);
  const list = useQuery({ queryKey: ["conversations", "tutor"], queryFn: () => api<Page<Conversation>>("/tutor/conversations?mode=tutor&page_size=50") });
  const create = useMutation({
    mutationFn: () => api<Conversation>("/tutor/conversations", { json: { mode: "tutor" } }),
    onSuccess: (c) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      setActive(c.id);
    },
    onError: (err) => push({ tone: "error", title: "Couldn't start a chat", description: errorMessage(err) }),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api(`/tutor/conversations/${id}`, { method: "DELETE" }),
    onSuccess: (_, id) => {
      if (active === id) setActive(null);
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
  const current = active ?? list.data?.items[0]?.id ?? null;

  return (
    <div>
      <PageHeader
        title="SI Tutor"
        description="Ask about grammar or vocabulary, or paste a sentence to check. The tutor knows your recent mistakes and goals, and gives hints before answers."
        action={
          <Button onClick={() => create.mutate()} loading={create.isPending}>
            <Plus className="size-4" /> New chat
          </Button>
        }
      />
      <div className="grid gap-4 lg:grid-cols-4">
        <Card className="h-fit lg:col-span-1">
          {list.isLoading ? (
            <div className="p-4">
              <Skeleton className="h-32" />
            </div>
          ) : list.error ? (
            <div className="p-4">
              <ErrorState error={list.error} onRetry={() => list.refetch()} />
            </div>
          ) : list.data?.items.length ? (
            <ul className="divide-y divide-border">
              {list.data.items.map((c) => (
                <li key={c.id} className={cn("group flex items-center gap-2 px-3 py-2.5", current === c.id && "bg-primary-soft/60")}>
                  <button onClick={() => setActive(c.id)} className="min-w-0 flex-1 text-left">
                    <p className="truncate text-sm font-medium">{c.title}</p>
                    <p className="text-xs text-muted-foreground">{relativeTime(c.updated_at)}</p>
                  </button>
                  <button onClick={() => remove.mutate(c.id)} className="rounded p-1 text-muted-foreground opacity-0 hover:bg-muted group-hover:opacity-100 focus:opacity-100" aria-label={`Delete ${c.title}`}>
                    <Trash2 className="size-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <div className="p-4 text-sm text-muted-foreground">No chats yet.</div>
          )}
        </Card>
        <div className="lg:col-span-3">
          {current ? (
            <Chat key={current} conversationId={current} suggestions={SUGGESTIONS} />
          ) : (
            <EmptyState
              icon={<MessageCircle className="size-5" />}
              title="Start a conversation with your tutor"
              description='Try "check: She go to school every days." — you get a hint first, then the correction when you ask.'
              action={
                <Button onClick={() => create.mutate()} loading={create.isPending}>
                  Start chatting
                </Button>
              }
            />
          )}
        </div>
      </div>
    </div>
  );
}
