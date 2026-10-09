import { useQuery } from "@tanstack/react-query";
import { useLocalSearchParams } from "expo-router";
import { useState } from "react";

import { ReviewSession } from "@/components/review-session";
import { QueryView, Screen } from "@/components/ui";
import { api } from "@/lib/api";
import type { VocabToday } from "@/lib/types";

export default function VocabularyReviewScreen() {
  const { focus } = useLocalSearchParams<{ focus?: string }>();
  const [round, setRound] = useState(0);
  // Always a fresh session (exercises are rebuilt from the current schedule), never a cached one.
  const session = useQuery({
    queryKey: ["vocab-session", focus ?? null, round],
    queryFn: () => api<VocabToday>(`/vocabulary/today${focus ? `?focus=${focus}` : ""}`),
    staleTime: Infinity,
    gcTime: 0,
  });
  return (
    <QueryView query={session} loadingLabel="Choosing today's words…">
      {(data) => (
        <Screen>
          <ReviewSession key={data.started_at} session={data} onFinished={() => setRound((r) => r + 1)} />
        </Screen>
      )}
    </QueryView>
  );
}
