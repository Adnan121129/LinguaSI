import type { ReactNode } from "react";
import { View } from "react-native";

import { Text, type Tone } from "@/components/ui";

/** Renders the small Markdown subset used in tutor replies (**bold**, _italic_, "- " lists) as native text. */
function inline(text: string, tone: Tone): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|_[^_]+_)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**"))
      return (
        <Text key={i} weight="700" tone={tone}>
          {part.slice(2, -2)}
        </Text>
      );
    if (part.length > 2 && part.startsWith("_") && part.endsWith("_"))
      return (
        <Text key={i} tone={tone} style={{ fontStyle: "italic" }}>
          {part.slice(1, -1)}
        </Text>
      );
    return part;
  });
}

export function RichText({ text, tone = "default" }: { text: string; tone?: Tone }) {
  const blocks: ReactNode[] = [];
  let list: string[] = [];
  const flush = () => {
    if (!list.length) return;
    blocks.push(
      <View key={`l${blocks.length}`} style={{ gap: 2 }}>
        {list.map((item, i) => (
          <Text key={i} tone={tone}>
            {"•  "}
            {inline(item, tone)}
          </Text>
        ))}
      </View>,
    );
    list = [];
  };
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (/^[-•]\s+/.test(trimmed)) {
      list.push(trimmed.replace(/^[-•]\s+/, ""));
      continue;
    }
    flush();
    if (trimmed)
      blocks.push(
        <Text key={`p${blocks.length}`} tone={tone}>
          {inline(trimmed, tone)}
        </Text>,
      );
  }
  flush();
  return <View style={{ gap: 6 }}>{blocks}</View>;
}
