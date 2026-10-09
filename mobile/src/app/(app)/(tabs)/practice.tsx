import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { BookOpen, FlaskConical, Headphones, Mic, PenLine, Puzzle, Target } from "lucide-react-native";

import { Badge, Card, Divider, ListRow, PageHeader, Screen, Text } from "@/components/ui";
import { useRefetchOnFocus } from "@/hooks/use-refetch-on-focus";
import { api } from "@/lib/api";
import type { Page, PracticeSet } from "@/lib/types";
import { relativeTime } from "@/lib/utils";

export default function PracticeTab() {
  const recent = useQuery({ queryKey: ["practice-list"], queryFn: () => api<Page<PracticeSet>>("/practice/sets?page_size=5") });
  useRefetchOnFocus(recent.refetch);
  return (
    <Screen safeTop refreshing={recent.isRefetching} onRefresh={recent.refetch}>
      <PageHeader title="Practice" subtitle="Every activity feeds the same learner profile, so each skill helps the others." />
      <Card style={{ gap: 0, paddingVertical: 4 }}>
        <ListRow icon={PenLine} title="Writing" subtitle="IELTS Task 1 and 2 with tutor hints and an AI estimated band" onPress={() => router.push("/writing")} />
        <Divider />
        <ListRow icon={Mic} title="Speaking" subtitle="Mock test Parts 1–3: record, replay and get feedback" onPress={() => router.push("/speaking")} />
        <Divider />
        <ListRow icon={BookOpen} title="Reading" subtitle="Original passages with IELTS question types and evidence" onPress={() => router.push("/reading")} />
        <Divider />
        <ListRow icon={Headphones} title="Listening" subtitle="Conversations and talks at your level" onPress={() => router.push("/listening")} />
      </Card>
      <Card style={{ gap: 0, paddingVertical: 4 }}>
        <ListRow icon={Target} tone="danger" title="My Mistakes" subtitle="Recurring errors, revision and repair challenges" onPress={() => router.push("/mistakes")} />
        <Divider />
        <ListRow icon={Puzzle} tone="accent" title="Targeted practice" subtitle="Grammar and vocabulary drills on a topic you choose" onPress={() => router.push("/practice/new")} />
        <Divider />
        <ListRow icon={FlaskConical} tone="success" title="English Lab" subtitle="Daily phrase, pronunciation, conversation and sentence building" onPress={() => router.push("/lab")} />
      </Card>
      {recent.data?.items.length ? (
        <Card style={{ gap: 0, paddingVertical: 4 }}>
          <Text variant="subheading" style={{ paddingTop: 10 }}>Recent practice</Text>
          {recent.data.items.map((ps) => (
            <ListRow
              key={ps.id}
              title={ps.title}
              subtitle={ps.status === "completed" ? `${ps.score}/${ps.total} correct · ${relativeTime(ps.completed_at ?? ps.created_at)}` : `${ps.items.length} questions · about ${ps.estimated_minutes} min`}
              right={<Badge tone={ps.status === "completed" ? "success" : "primary"} label={ps.status === "completed" ? "Done" : "Continue"} />}
              onPress={() => router.push(`/practice/${ps.id}`)}
            />
          ))}
        </Card>
      ) : null}
    </Screen>
  );
}
