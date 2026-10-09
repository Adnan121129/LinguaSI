import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { BookOpen, CalendarDays, FlaskConical, Headphones, Library, MessagesSquare, Mic, PenLine, Puzzle, Shuffle, type LucideIcon } from "lucide-react-native";
import { Fragment } from "react";

import { Card, Divider, ListRow, QueryView, Screen, Text } from "@/components/ui";
import { api } from "@/lib/api";
import { appHref } from "@/lib/routes";
import type { LabOverview } from "@/lib/types";

const ICONS: Record<string, LucideIcon> = {
  grammar: Puzzle,
  vocabulary: Library,
  pronunciation: Mic,
  conversation: MessagesSquare,
  sentence_building: Shuffle,
  reading: BookOpen,
  listening: Headphones,
  writing: PenLine,
  daily: CalendarDays,
};

export default function LabScreen() {
  const lab = useQuery({ queryKey: ["lab"], queryFn: () => api<LabOverview>("/lab") });
  return (
    <QueryView query={lab}>
      {(data) => (
        <Screen refreshing={lab.isRefetching} onRefresh={lab.refetch}>
          <Text tone="muted">Everyday English beyond the exam: grammar, pronunciation, conversation, sentence building and a phrase a day.</Text>
          <Card tone="primary" onPress={() => router.push("/lab/daily")}>
            <Text variant="label" tone="primary">Phrase of the day</Text>
            <Text variant="title">{data.daily_phrase.phrase}</Text>
            <Text>{data.daily_phrase.meaning}</Text>
            <Text variant="small" tone="muted" style={{ fontStyle: "italic" }}>“{data.daily_phrase.example}”</Text>
            <Text variant="small" tone="primary" weight="600">Practise today&apos;s phrase →</Text>
          </Card>
          <Card style={{ gap: 0, paddingVertical: 4 }}>
            {data.sections.map((section, i) => (
              <Fragment key={section.key}>
                {i ? <Divider /> : null}
                <ListRow
                  icon={ICONS[section.key] ?? FlaskConical}
                  title={section.title}
                  subtitle={`${section.description}${section.count !== null ? ` · ${section.count} available` : ""}`}
                  onPress={() => router.push(appHref(section.route))}
                />
              </Fragment>
            ))}
          </Card>
        </Screen>
      )}
    </QueryView>
  );
}
