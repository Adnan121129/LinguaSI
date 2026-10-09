import { router, Stack } from "expo-router";
import { useEffect } from "react";

import { takePendingRoute } from "@/lib/pending-route";
import { appHref } from "@/lib/routes";
import { useTheme } from "@/lib/theme";

export const unstable_settings = { initialRouteName: "(tabs)" };

/** Every signed-in screen. Tabs hold the five main areas; everything else opens on top with a back button. */
export default function AppLayout() {
  const { colors } = useTheme();
  useEffect(() => {
    const next = takePendingRoute();
    if (next) router.push(appHref(next));
  }, []);
  return (
    <Stack
      screenOptions={{
        headerShadowVisible: false,
        headerStyle: { backgroundColor: colors.background },
        headerTintColor: colors.primary,
        headerTitleStyle: { color: colors.foreground, fontWeight: "600" },
        headerBackButtonDisplayMode: "minimal",
        contentStyle: { backgroundColor: colors.background },
      }}
    >
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="diagnostic" options={{ title: "Diagnostic" }} />
      <Stack.Screen name="writing/index" options={{ title: "Writing" }} />
      <Stack.Screen name="writing/[id]" options={{ title: "Writing" }} />
      <Stack.Screen name="speaking/index" options={{ title: "Speaking" }} />
      <Stack.Screen name="speaking/[id]" options={{ title: "Speaking test" }} />
      <Stack.Screen name="reading/index" options={{ title: "Reading" }} />
      <Stack.Screen name="reading/[id]" options={{ title: "Reading" }} />
      <Stack.Screen name="listening/index" options={{ title: "Listening" }} />
      <Stack.Screen name="listening/[id]" options={{ title: "Listening" }} />
      <Stack.Screen name="vocabulary/review" options={{ title: "Vocabulary review" }} />
      <Stack.Screen name="mistakes" options={{ title: "My Mistakes" }} />
      <Stack.Screen name="practice/new" options={{ title: "New practice" }} />
      <Stack.Screen name="practice/[id]" options={{ title: "Practice" }} />
      <Stack.Screen name="lab/index" options={{ title: "English Lab" }} />
      <Stack.Screen name="lab/daily" options={{ title: "Daily English" }} />
      <Stack.Screen name="lab/grammar" options={{ title: "Grammar" }} />
      <Stack.Screen name="lab/sentence-building" options={{ title: "Sentence building" }} />
      <Stack.Screen name="lab/pronunciation" options={{ title: "Pronunciation" }} />
      <Stack.Screen name="lab/conversation" options={{ title: "Conversation" }} />
      <Stack.Screen name="tutor/[id]" options={{ title: "SI Tutor" }} />
      <Stack.Screen name="progress" options={{ title: "Progress" }} />
      <Stack.Screen name="achievements" options={{ title: "Achievements" }} />
      <Stack.Screen name="settings" options={{ title: "Settings" }} />
    </Stack>
  );
}
