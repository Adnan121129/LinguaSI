import { useQuery } from "@tanstack/react-query";
import { Stack, useLocalSearchParams } from "expo-router";
import { View } from "react-native";

import { PracticeRunner } from "@/components/practice-runner";
import { QueryView, Screen, Text } from "@/components/ui";
import { api } from "@/lib/api";
import type { PracticeSet } from "@/lib/types";

export default function PracticeScreen() {
  const { id, from } = useLocalSearchParams<{ id: string; from?: string }>();
  const practiceId = Number(id);
  const practice = useQuery({ queryKey: ["practice", practiceId], queryFn: () => api<PracticeSet>(`/practice/sets/${practiceId}`) });
  return (
    <QueryView query={practice}>
      {(data) => (
        <Screen>
          <Stack.Screen options={{ title: data.title }} />
          <View style={{ gap: 4 }}>
            <Text variant="heading">{data.title}</Text>
            <Text variant="small" tone="muted">
              {data.description} · about {data.estimated_minutes} min
            </Text>
          </View>
          <PracticeRunner key={data.id} practice={data} exit={from === "lab" ? { href: "/lab", label: "Back to the English Lab" } : undefined} />
        </Screen>
      )}
    </QueryView>
  );
}
