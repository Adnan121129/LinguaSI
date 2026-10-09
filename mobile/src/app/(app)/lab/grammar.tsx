import { TopicPicker } from "@/components/topic-picker";
import { Screen, Text } from "@/components/ui";

export default function LabGrammarScreen() {
  return (
    <Screen>
      <Text tone="muted">Short, focused drills. SI mixes in sentences from your own writing and speaking whenever it can.</Text>
      <TopicPicker from="lab" />
    </Screen>
  );
}
