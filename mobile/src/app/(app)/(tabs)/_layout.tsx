import { Tabs } from "expo-router/js-tabs";
import { Bot, Dumbbell, House, Library, UserRound } from "lucide-react-native";

import { useTheme } from "@/lib/theme";

/** Bottom navigation for the most important mobile functions (the web sidebar, simplified). */
export default function TabsLayout() {
  const { colors } = useTheme();
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.mutedForeground,
        tabBarStyle: { backgroundColor: colors.card, borderTopColor: colors.border },
        tabBarLabelStyle: { fontSize: 11, fontWeight: "600" },
      }}
    >
      <Tabs.Screen name="index" options={{ title: "Home", tabBarIcon: ({ color, size }) => <House color={color} size={size} /> }} />
      <Tabs.Screen name="practice" options={{ title: "Practice", tabBarIcon: ({ color, size }) => <Dumbbell color={color} size={size} /> }} />
      <Tabs.Screen name="vocabulary" options={{ title: "Vocabulary", tabBarIcon: ({ color, size }) => <Library color={color} size={size} /> }} />
      <Tabs.Screen name="tutor" options={{ title: "Tutor", tabBarIcon: ({ color, size }) => <Bot color={color} size={size} /> }} />
      <Tabs.Screen name="me" options={{ title: "Me", tabBarIcon: ({ color, size }) => <UserRound color={color} size={size} /> }} />
    </Tabs>
  );
}
