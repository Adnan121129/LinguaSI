import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { PracticeRunner } from "@/components/practice-runner";
import { Button, ErrorState, Loading, Screen, Text } from "@/components/ui";
import { api } from "@/lib/api";
import type { PracticeSet } from "@/lib/types";

export default function SentenceBuildingScreen() {
  const create = useMutation({ mutationFn: () => api<PracticeSet>("/lab/sentence-building", { method: "POST" }) });
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    create.mutate();
  }, [create]);

  if (create.isPending) return <Loading label="Building sentences…" />;
  return (
    <Screen>
      <Text tone="muted">Rebuild natural sentences from scrambled words — great for word order and collocations.</Text>
      {create.error ? <ErrorState error={create.error} onRetry={() => create.mutate()} /> : null}
      {create.data ? (
        <>
          <PracticeRunner key={create.data.id} practice={create.data} exit={{ href: "/lab", label: "Back to the English Lab" }} />
          <Button title="New set" variant="outline" onPress={() => create.mutate()} />
        </>
      ) : null}
    </Screen>
  );
}
