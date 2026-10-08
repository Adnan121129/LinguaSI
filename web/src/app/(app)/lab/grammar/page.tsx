import { TopicPicker } from "@/components/practice/topic-picker";
import { PageHeader } from "@/components/ui";

export default function LabGrammarPage() {
  return (
    <div>
      <PageHeader title="Grammar workshop" description="Short, focused drills. SI mixes in sentences from your own writing and speaking whenever it can." />
      <TopicPicker />
    </div>
  );
}
