import { useLocalSearchParams } from "expo-router";
import { useEffect, useRef, useState } from "react";

import { openPractice, TopicPicker } from "@/components/topic-picker";
import { ErrorState, Loading, PageHeader, Screen } from "@/components/ui";

export default function NewPracticeScreen() {
  const { focus, from } = useLocalSearchParams<{ focus?: string; from?: string }>();
  const [error, setError] = useState<unknown>(null);
  const started = useRef(false);

  // Recommendations link here with ?focus=...; build that set straight away in place of this screen.
  useEffect(() => {
    if (!focus || started.current) return;
    started.current = true;
    openPractice(focus, { from, replace: true }).catch(setError);
  }, [focus, from]);

  if (focus) {
    return error ? (
      <Screen>
        <ErrorState error={error} />
      </Screen>
    ) : (
      <Loading label="Building your practice set…" />
    );
  }
  return (
    <Screen>
      <PageHeader title="Focused practice" subtitle="Pick a grammar or language area. Each set mixes sentences from your own work with targeted exercises." />
      <TopicPicker from={from} />
    </Screen>
  );
}
