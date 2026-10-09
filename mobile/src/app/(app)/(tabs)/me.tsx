import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { Award, ChartLine, LogOut, Settings, Target } from "lucide-react-native";
import { View } from "react-native";

import { BandValue } from "@/components/band";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button, Card, Divider, ListRow, ProgressBar, Row, Screen, Stat, StatGrid, Text } from "@/components/ui";
import { useMe } from "@/hooks/use-me";
import { useRefetchOnFocus } from "@/hooks/use-refetch-on-focus";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { confirmAction } from "@/lib/confirm";
import { useTheme } from "@/lib/theme";
import type { Dashboard } from "@/lib/types";

export default function MeTab() {
  const { colors } = useTheme();
  const { signOut } = useAuth();
  const { data: me } = useMe();
  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: () => api<Dashboard>("/dashboard") });
  useRefetchOnFocus(dashboard.refetch);
  const d = dashboard.data;
  return (
    <Screen safeTop refreshing={dashboard.isRefetching} onRefresh={dashboard.refetch}>
      <Row style={{ gap: 14 }}>
        <View style={{ width: 56, height: 56, borderRadius: 28, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" }}>
          <Text variant="title" tone="primary">{me?.name.slice(0, 1).toUpperCase()}</Text>
        </View>
        <View style={{ flex: 1, gap: 2 }}>
          <Text variant="heading">{me?.name}</Text>
          <Text variant="small" tone="muted">{me?.email}</Text>
        </View>
      </Row>
      {d ? (
        <Card>
          <StatGrid>
            {d.goal === "ielts" ? <BandValue band={d.estimated_band} target={d.target_band} size="sm" /> : <Stat label="AI Estimated Level" value={d.cefr ?? "—"} />}
            <Stat label="Streak" value={`${d.streak.current} day${d.streak.current === 1 ? "" : "s"}`} />
          </StatGrid>
          <Stat label={`Level ${d.level.level}`} value={d.level.title} />
          <ProgressBar value={d.level.progress * 100} label="Progress to next level" />
          <Text variant="caption" tone="muted">{d.level.xp.toLocaleString()} XP in total</Text>
        </Card>
      ) : null}
      <Card style={{ gap: 0, paddingVertical: 4 }}>
        <ListRow icon={ChartLine} title="Progress" subtitle="Bands, skills, vocabulary growth and consistency" onPress={() => router.push("/progress")} />
        <Divider />
        <ListRow icon={Award} tone="warning" title="Achievements" subtitle="Badges, weekly challenges and XP history" onPress={() => router.push("/achievements")} />
        <Divider />
        <ListRow icon={Target} tone="danger" title="My Mistakes" subtitle="What you repeatedly get wrong, and how it's improving" onPress={() => router.push("/mistakes")} />
        <Divider />
        <ListRow icon={Settings} tone="muted" title="Settings" subtitle="Goals, routine, password and account" onPress={() => router.push("/settings")} />
      </Card>
      <Card>
        <Text variant="subheading">Appearance</Text>
        <ThemeToggle />
      </Card>
      <Button title="Sign out" variant="outline" icon={LogOut} onPress={() => confirmAction("Sign out?", "You can sign back in at any time; your progress is saved.", signOut, "Sign out")} />
    </Screen>
  );
}
