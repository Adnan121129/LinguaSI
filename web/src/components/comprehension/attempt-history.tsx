"use client";

import Link from "next/link";

import { BandValue } from "@/components/band";
import { Badge } from "@/components/ui";
import type { AttemptSummary } from "@/lib/types";
import { formatDate, percent } from "@/lib/utils";

export const READING_TYPES = ["multiple_choice", "true_false_not_given", "yes_no_not_given", "matching_headings", "matching_information", "sentence_completion", "summary_completion", "short_answer"];

export function AttemptHistory({ items, base }: { items: AttemptSummary[]; base: string }) {
  return (
    <ul className="divide-y divide-border">
      {items.map((a) => (
        <li key={a.id}>
          <Link href={`${base}/${a.id}`} className="flex flex-wrap items-center gap-4 py-3 hover:bg-muted/40">
            <div className="min-w-0 flex-1">
              <p className="font-medium">{a.title}</p>
              <p className="text-sm text-muted-foreground">
                Level {a.difficulty} · {a.status === "submitted" ? `${a.correct}/${a.total} correct (${percent(a.accuracy)})` : "In progress"} · {formatDate(a.submitted_at ?? a.started_at)}
              </p>
            </div>
            {a.band !== null ? <BandValue band={a.band} size="sm" label={null} /> : <Badge>Continue</Badge>}
          </Link>
        </li>
      ))}
    </ul>
  );
}

export const LISTENING_TYPES = ["multiple_choice", "form_completion", "note_completion", "sentence_completion", "short_answer"];
