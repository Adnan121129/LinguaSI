import { Stack, useLocalSearchParams } from "expo-router";

import { Chat } from "@/components/chat";

const SUGGESTIONS = ["check: Yesterday I go to the library and borrow three books.", 'What does "mitigate" mean?', "What should I focus on this week?", "Explain the present perfect"];

export default function TutorChatScreen() {
  const { id, mode } = useLocalSearchParams<{ id: string; mode?: string }>();
  const conversation = mode === "conversation";
  return (
    <>
      <Stack.Screen options={{ title: conversation ? "Conversation" : "SI Tutor" }} />
      <Chat key={id} conversationId={Number(id)} suggestions={conversation ? [] : SUGGESTIONS} />
    </>
  );
}
