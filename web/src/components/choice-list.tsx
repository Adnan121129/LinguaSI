"use client";

import { cn } from "@/lib/utils";

/** Accessible single-choice list (radio group) styled as tappable cards. */
export function ChoiceList({
  name,
  options,
  value,
  onChange,
  disabled,
  correct,
}: {
  name: string;
  options: string[];
  value: string | undefined;
  onChange: (value: string) => void;
  disabled?: boolean;
  correct?: string | null;
}) {
  return (
    <div role="radiogroup" className="grid gap-2">
      {options.map((option) => {
        const selected = value === option;
        const isCorrect = correct !== undefined && correct !== null && option.trim().toLowerCase() === correct.trim().toLowerCase();
        return (
          <label
            key={option}
            className={cn(
              "flex cursor-pointer items-center gap-3 rounded-xl border px-3.5 py-2.5 text-sm transition",
              selected ? "border-primary bg-primary-soft" : "border-border hover:bg-muted",
              disabled && "cursor-default",
              correct !== undefined && isCorrect && "border-success bg-success-soft",
              correct !== undefined && selected && !isCorrect && "border-danger bg-danger-soft",
            )}
          >
            <input type="radio" name={name} value={option} checked={selected} disabled={disabled} onChange={() => onChange(option)} className="accent-[var(--primary)]" />
            <span>{option}</span>
          </label>
        );
      })}
    </div>
  );
}
