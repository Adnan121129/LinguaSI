import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { MessageCircle, Plus, Trash2 } from "lucide-react-native";
import { ActivityIndicator, Pressable, View } from "react-native";

import { useToast } from "@/components/toast";
import { Button, Card, EmptyState, ErrorState, PageHeader, Row, Screen, Text } from "@/components/ui";
import { useRefetchOnFocus } from "@/hooks/use-refetch-on-focus";
import { api, errorMessage } from "@/lib/api";
import { confirmAction } from "@/lib/confirm";
import { useTheme } from "@/lib/theme";
import type { Conversation, Page } from "@/lib/types";
import { relativeTime } from "@/lib/utils";

export default function TutorTab() {
  const { colors } = useTheme();
  const queryClient = useQueryClient();
  const { push } = useToast();
  const list = useQuery({ queryKey: ["conversations", "tutor"], queryFn: () => api<Page<Conversation>>("/tutor/conversations?mode=tutor&page_size=50") });
  useRefetchOnFocus(list.refetch);
  const create = useMutation({
    mutationFn: () => api<Conversation>("/tutor/conversations", { json: { mode: "tutor" } }),
    onSuccess: (c) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      router.push(`/tutor/${c.id}`);
    },
    onError: (err) => push({ tone: "error", title: "Couldn't start a chat", description: errorMessage(err) }),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api(`/tutor/conversations/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["conversations"] }),
    onError: (err) => push({ tone: "error", title: "Couldn't delete the chat", description: errorMessage(err) }),
  });

  return (
    <Screen safeTop refreshing={list.isRefetching} onRefresh={list.refetch}>
      <PageHeader title="SI Tutor" subtitle="Ask about grammar or vocabulary, or check a sentence. The tutor knows your recent mistakes and gives hints before answers." />
      <Button title="New chat" icon={Plus} loading={create.isPending} onPress={() => create.mutate()} />
      {list.isLoading ? (
        <ActivityIndicator color={colors.primary} />
      ) : list.error ? (
        <ErrorState error={list.error} onRetry={() => list.refetch()} />
      ) : list.data?.items.length ? (
        <Card style={{ paddingVertical: 4, gap: 0 }}>
          {list.data.items.map((c, i) => (
            <View key={c.id} style={{ flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 12, borderTopWidth: i ? 1 : 0, borderTopColor: colors.border }}>
              <Pressable onPress={() => router.push(`/tutor/${c.id}`)} accessibilityRole="button" style={{ flex: 1, gap: 2 }}>
                <Text weight="600" numberOfLines={1}>{c.title}</Text>
                <Text variant="caption" tone="muted">{relativeTime(c.updated_at)}</Text>
              </Pressable>
              <Pressable onPress={() => confirmAction("Delete this chat?", c.title, () => remove.mutate(c.id))} hitSlop={10} accessibilityRole="button" accessibilityLabel={`Delete ${c.title}`}>
                <Trash2 size={17} color={colors.mutedForeground} />
              </Pressable>
            </View>
          ))}
        </Card>
      ) : (
        <EmptyState icon={MessageCircle} title="Start a conversation with your tutor" description='Try "check: She go to school every days." — you get a hint first, then the correction when you ask.' />
      )}
      <Row>
        <Text variant="caption" tone="muted">The tutor explains and guides; it doesn&apos;t write your essays for you.</Text>
      </Row>
    </Screen>
  );
}
