import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Send, Target } from "lucide-react-native";
import { useRef, useState } from "react";
import { FlatList, KeyboardAvoidingView, Platform, Pressable, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { RichText } from "@/components/rich-text";
import { useToast } from "@/components/toast";
import { Badge, ErrorState, Loading, Row, Screen, Text } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import type { ActivityOutcome, Conversation, TutorMessage } from "@/lib/types";

const INTENT_LABELS: Record<string, string> = { sentence_check: "Sentence check", reveal: "Corrections", vocabulary: "Word help" };

/** Chat with the SI Tutor or a Lab role-play partner. */
export function Chat({ conversationId, suggestions = [] }: { conversationId: number; suggestions?: string[] }) {
  const queryClient = useQueryClient();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { push, celebrate } = useToast();
  const [draft, setDraft] = useState("");
  const list = useRef<FlatList<TutorMessage>>(null);
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

  if (isLoading) return <Loading />;
  if (error || !data)
    return (
      <Screen>
        <ErrorState error={error} onRetry={() => refetch()} />
      </Screen>
    );

  const scenario = data.scenario_info;
  const messages = data.messages ?? [];
  const submit = () => draft.trim() && !send.isPending && send.mutate(draft.trim());

  return (
    <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} keyboardVerticalOffset={Platform.OS === "ios" ? 90 : 0} style={{ flex: 1, backgroundColor: colors.background }}>
      {scenario ? (
        <View style={{ padding: 14, gap: 4, borderBottomWidth: 1, borderBottomColor: colors.border }}>
          <Row>
            <Target size={15} color={colors.primary} />
            <Text weight="600" style={{ flex: 1 }}>{scenario.goal}</Text>
          </Row>
          <Text variant="small" tone="muted">
            You&apos;re talking to {scenario.ai_role}. Useful phrases: {scenario.phrases.join(" · ")}
          </Text>
        </View>
      ) : null}
      <FlatList
        ref={list}
        data={messages}
        keyExtractor={(m) => String(m.id)}
        contentContainerStyle={{ padding: 14, gap: 12 }}
        onContentSizeChange={() => list.current?.scrollToEnd({ animated: true })}
        renderItem={({ item: m }) => {
          const mine = m.role === "user";
          const intent = typeof m.meta?.intent === "string" ? INTENT_LABELS[m.meta.intent] : undefined;
          return (
            <View style={{ flexDirection: mine ? "row-reverse" : "row", gap: 8, alignItems: "flex-start" }}>
              {!mine ? (
                <View style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" }}>
                  <Bot size={16} color={colors.primary} />
                </View>
              ) : null}
              <View style={{ maxWidth: "84%", borderRadius: 18, paddingHorizontal: 14, paddingVertical: 10, gap: 6, backgroundColor: mine ? colors.primary : colors.card, borderWidth: mine ? 0 : 1, borderColor: colors.border }}>
                {intent ? <Badge tone="primary" label={intent} /> : null}
                {mine ? <Text style={{ color: colors.primaryForeground }}>{m.content}</Text> : <RichText text={m.content} />}
              </View>
            </View>
          );
        }}
        ListFooterComponent={
          send.isPending ? (
            <Row style={{ marginTop: 12 }}>
              <View style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" }}>
                <Bot size={16} color={colors.primary} />
              </View>
              <Text tone="muted">Thinking…</Text>
            </Row>
          ) : null
        }
      />
      {suggestions.length && messages.length <= 1 ? (
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8, paddingHorizontal: 14, paddingBottom: 8 }}>
          {suggestions.map((s) => (
            <Pressable key={s} onPress={() => setDraft(s)} accessibilityRole="button" style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 6 }}>
              <Text variant="caption" tone="muted">{s}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}
      <View style={{ flexDirection: "row", alignItems: "flex-end", gap: 8, padding: 10, paddingBottom: 10 + insets.bottom, borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.card }}>
        <TextInput
          value={draft}
          onChangeText={setDraft}
          placeholder={scenario ? "Reply in English…" : 'Ask a question, or write "check: your sentence"'}
          placeholderTextColor={colors.mutedForeground}
          accessibilityLabel="Message"
          multiline
          maxLength={2000}
          style={{ flex: 1, maxHeight: 120, minHeight: 42, borderRadius: 14, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.background, color: colors.foreground, paddingHorizontal: 12, paddingTop: 10, paddingBottom: 10, fontSize: 15 }}
        />
        <Pressable
          onPress={submit}
          disabled={!draft.trim() || send.isPending}
          accessibilityRole="button"
          accessibilityLabel="Send message"
          style={{ width: 44, height: 44, borderRadius: 14, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center", opacity: !draft.trim() || send.isPending ? 0.5 : 1 }}
        >
          <Send size={18} color={colors.primaryForeground} />
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}
