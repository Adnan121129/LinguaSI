import { useMutation, useQuery } from "@tanstack/react-query";
import { Volume2 } from "lucide-react-native";

import { PracticeRunner } from "@/components/practice-runner";
import { Button, Card, ErrorState, QueryView, Row, Screen, Text } from "@/components/ui";
import { api } from "@/lib/api";
import { speak } from "@/lib/speech";
import type { LabOverview, PracticeSet } from "@/lib/types";

export default function DailyEnglishScreen() {
  const phrase = useQuery({ queryKey: ["lab-daily"], queryFn: () => api<LabOverview["daily_phrase"]>("/lab/daily") });
  const quiz = useMutation({ mutationFn: () => api<PracticeSet>("/lab/daily/quiz", { method: "POST" }) });
  return (
    <QueryView query={phrase}>
      {(p) => (
        <Screen>
          <Text tone="muted">One useful everyday expression a day, plus a quick quiz that recycles earlier phrases.</Text>
          <Card>
            <Row style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
              <Text variant="title" style={{ flex: 1 }}>{p.phrase}</Text>
              <Button title="Listen" icon={Volume2} size="sm" variant="ghost" onPress={() => speak(`${p.phrase}. ${p.example}`, { rate: 0.95 })} accessibilityLabel="Listen to the phrase" />
            </Row>
            <Text variant="subheading" weight="400">{p.meaning}</Text>
            <Text tone="muted" style={{ fontStyle: "italic" }}>“{p.example}”</Text>
          </Card>
          {quiz.data ? (
            <PracticeRunner key={quiz.data.id} practice={quiz.data} exit={{ href: "/lab", label: "Back to the English Lab" }} />
          ) : (
            <>
              {quiz.error ? <ErrorState error={quiz.error} /> : null}
              <Button title="Take the 1-minute quiz" size="lg" loading={quiz.isPending} onPress={() => quiz.mutate()} />
            </>
          )}
        </Screen>
      )}
    </QueryView>
  );
}
