import { Fragment, type ReactNode } from "react";

/** Renders the small Markdown subset used in tutor replies (**bold**, _italic_, "- " lists) without injecting HTML. */
function inline(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|_[^_]+_)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.length > 2 && part.startsWith("_") && part.endsWith("_")) return <em key={i}>{part.slice(1, -1)}</em>;
    return <Fragment key={i}>{part}</Fragment>;
  });
}

export function RichText({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let list: string[] = [];
  const flush = () => {
    if (list.length) {
      blocks.push(
        <ul key={`l${blocks.length}`} className="my-1 list-disc space-y-0.5 pl-5">
          {list.map((item, i) => (
            <li key={i}>{inline(item)}</li>
          ))}
        </ul>,
      );
      list = [];
    }
  };
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (/^[-•]\s+/.test(trimmed)) {
      list.push(trimmed.replace(/^[-•]\s+/, ""));
      continue;
    }
    flush();
    if (trimmed) blocks.push(<p key={`p${blocks.length}`}>{inline(trimmed)}</p>);
  }
  flush();
  return <div className="space-y-2">{blocks}</div>;
}
