import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { MessagesSquare } from "lucide-react-native";

import { useToast } from "@/components/toast";
import { Badge, Button, Card, ListRow, QueryView, Row, Screen, Text } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { Conversation, Page, ScenarioInfo } from "@/lib/types";
import { relativeTime } from "@/lib/utils";

export default function ConversationScreen() {
  const queryClient = useQueryClient();
  const { push } = useToast();
  const scenarios = useQuery({ queryKey: ["scenarios"], queryFn: () => api<ScenarioInfo[]>("/lab/scenarios") });
  const previous = useQuery({ queryKey: ["conversations", "conversation"], queryFn: () => api<Page<Conversation>>("/tutor/conversations?mode=conversation&page_size=10") });
  const start = useMutation({
    mutationFn: (scenarioId: string) => api<Conversation>("/tutor/conversations", { json: { mode: "conversation", scenario_id: scenarioId } }),
    onSuccess: (c) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      router.push(`/tutor/${c.id}?mode=conversation`);
    },
    onError: (err) => push({ tone: "error", title: "Couldn't start the conversation", description: errorMessage(err) }),
  });
  return (
    <QueryView query={scenarios}>
      {(list) => (
        <Screen>
          <Text tone="muted">Role-play real situations with an SI partner who stays in character and adapts to your level. Four replies count as an English Lab session.</Text>
          {list.map((s) => (
            <Card key={s.id}>
              <Row style={{ justifyContent: "space-between" }}>
                <Text weight="600" style={{ flex: 1 }}>{s.title}</Text>
                <Badge label={s.level} />
              </Row>
              <Text variant="small" tone="muted">{s.goal}</Text>
              <Text variant="caption" tone="muted">Partner: {s.ai_role}</Text>
              <Button title="Start" icon={MessagesSquare} size="sm" loading={start.isPending && start.variables === s.id} disabled={start.isPending} onPress={() => start.mutate(s.id)} style={{ alignSelf: "flex-start" }} />
            </Card>
          ))}
          {previous.data?.items.length ? (
            <Card style={{ gap: 0, paddingVertical: 4 }}>
              <Text variant="subheading" style={{ paddingTop: 10 }}>Continue a conversation</Text>
              {previous.data.items.map((c) => (
                <ListRow key={c.id} title={c.title} subtitle={relativeTime(c.updated_at)} onPress={() => router.push(`/tutor/${c.id}?mode=conversation`)} />
              ))}
            </Card>
          ) : null}
        </Screen>
      )}
    </QueryView>
  );
}
