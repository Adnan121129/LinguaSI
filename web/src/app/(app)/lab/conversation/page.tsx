"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, MessagesSquare } from "lucide-react";
import { useState } from "react";

import { Chat } from "@/components/chat";
import { useToast } from "@/components/providers/toast";
import { Badge, Button, Card, CardBody, ErrorState, PageHeader, PageSkeleton } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { Conversation, Page, ScenarioInfo } from "@/lib/types";
import { relativeTime } from "@/lib/utils";

export default function ConversationPage() {
  const queryClient = useQueryClient();
  const { push } = useToast();
  const [active, setActive] = useState<number | null>(null);
  const scenarios = useQuery({ queryKey: ["scenarios"], queryFn: () => api<ScenarioInfo[]>("/lab/scenarios") });
  const previous = useQuery({ queryKey: ["conversations", "conversation"], queryFn: () => api<Page<Conversation>>("/tutor/conversations?mode=conversation&page_size=10") });
  const start = useMutation({
    mutationFn: (scenarioId: string) => api<Conversation>("/tutor/conversations", { json: { mode: "conversation", scenario_id: scenarioId } }),
    onSuccess: (c) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      setActive(c.id);
    },
    onError: (err) => push({ tone: "error", title: "Couldn't start the conversation", description: errorMessage(err) }),
  });

  if (active) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <Button variant="ghost" size="sm" onClick={() => setActive(null)}>
          <ArrowLeft className="size-4" /> All scenarios
        </Button>
        <Chat conversationId={active} />
        <p className="text-xs text-muted-foreground">After four replies the conversation counts as an English Lab session towards your mission.</p>
      </div>
    );
  }
  if (scenarios.isLoading) return <PageSkeleton />;
  if (scenarios.error || !scenarios.data) return <ErrorState error={scenarios.error} onRetry={() => scenarios.refetch()} />;
  return (
    <div className="space-y-6">
      <PageHeader title="Conversation practice" description="Role-play real situations with an SI partner who stays in character and adapts to your level." />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {scenarios.data.map((s) => (
          <Card key={s.id}>
            <CardBody className="flex h-full flex-col gap-2">
              <div className="flex items-center justify-between">
                <p className="font-semibold">{s.title}</p>
                <Badge>{s.level}</Badge>
              </div>
              <p className="text-sm text-muted-foreground">{s.goal}</p>
              <p className="text-xs text-muted-foreground">Partner: {s.ai_role}</p>
              <Button className="mt-auto w-fit" size="sm" onClick={() => start.mutate(s.id)} loading={start.isPending && start.variables === s.id}>
                <MessagesSquare className="size-4" /> Start
              </Button>
            </CardBody>
          </Card>
        ))}
      </div>
      {previous.data && previous.data.items.length > 0 && (
        <Card>
          <CardBody>
            <p className="mb-2 text-sm font-semibold">Continue a conversation</p>
            <ul className="divide-y divide-border">
              {previous.data.items.map((c) => (
                <li key={c.id}>
                  <button onClick={() => setActive(c.id)} className="flex w-full items-center justify-between py-2 text-left text-sm hover:text-primary">
                    <span>{c.title}</span>
                    <span className="text-xs text-muted-foreground">{relativeTime(c.updated_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
