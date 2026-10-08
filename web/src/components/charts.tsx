"use client";

import { Table2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from "recharts";

import { cn } from "@/lib/utils";

// Fixed categorical order: colour follows the entity (a skill always has the same colour), never its rank.
export const SERIES_COLORS: Record<string, string> = {
  overall: "var(--series-1)",
  reading: "var(--series-2)",
  listening: "var(--series-3)",
  writing: "var(--series-4)",
  speaking: "var(--series-5)",
  vocabulary: "var(--series-1)",
  grammar: "var(--series-2)",
  known: "var(--series-1)",
  mastered: "var(--series-3)",
};

const AXIS = { stroke: "var(--grid)", tick: { fill: "var(--axis-text)", fontSize: 12 }, tickLine: false } as const;

type Column = { key: string; label: string; format?: (value: unknown) => string };

/** Card wrapper: the title is the question the chart answers; every chart has a table view. */
export function ChartCard({
  question,
  description,
  children,
  rows,
  columns,
  legend,
  className,
}: {
  question: string;
  description?: ReactNode;
  children: ReactNode;
  rows: Record<string, unknown>[];
  columns: Column[];
  legend?: { label: string; color: string }[];
  className?: string;
}) {
  const [table, setTable] = useState(false);
  return (
    <section className={cn("rounded-2xl border border-border bg-card p-5 shadow-[var(--shadow-card)]", className)} aria-label={question}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold">{question}</h3>
          {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
        </div>
        <button
          onClick={() => setTable((t) => !t)}
          className="inline-flex shrink-0 items-center gap-1 rounded-lg px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-pressed={table}
        >
          <Table2 className="size-3.5" aria-hidden /> {table ? "Chart" : "Table"}
        </button>
      </div>
      {legend && legend.length > 1 && !table && (
        <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground" aria-label="Legend">
          {legend.map((item) => (
            <li key={item.label} className="flex items-center gap-1.5">
              <span className="inline-block h-0.5 w-4 rounded-full" style={{ background: item.color, height: 3 }} aria-hidden />
              {item.label}
            </li>
          ))}
        </ul>
      )}
      <div className="mt-4">
        {table ? (
          <div className="max-h-72 overflow-auto rounded-xl border border-border">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-muted text-xs uppercase text-muted-foreground">
                <tr>
                  {columns.map((c) => (
                    <th key={c.key} className="px-3 py-2 font-medium">
                      {c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={i} className="border-t border-border">
                    {columns.map((c) => (
                      <td key={c.key} className="px-3 py-1.5 tabular-nums">
                        {c.format ? c.format(row[c.key]) : row[c.key] === null || row[c.key] === undefined ? "—" : String(row[c.key])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          children
        )}
      </div>
    </section>
  );
}

function ChartTooltip({ active, payload, label, unit, labelFormat }: Partial<TooltipContentProps<number, string>> & { unit?: string; labelFormat?: (l: string) => string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-border bg-card px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-medium text-foreground">{labelFormat ? labelFormat(String(label)) : String(label)}</p>
      {payload.map((entry) => (
        <p key={String(entry.dataKey)} className="flex items-center gap-2 text-muted-foreground">
          <span className="inline-block size-2 rounded-full" style={{ background: entry.color }} aria-hidden />
          <span className="text-foreground">{entry.name}</span>
          <span className="ml-auto pl-3 tabular-nums text-foreground">
            {entry.value === null || entry.value === undefined ? "—" : `${entry.value}${unit ?? ""}`}
          </span>
        </p>
      ))}
    </div>
  );
}

export const shortDay = (day: string) => new Date(`${day}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
export const shortWeek = (week: string) => `W${week.split("-W")[1] ?? week}`;

export function MultiLineChart({
  data,
  xKey,
  series,
  yDomain,
  reference,
  unit,
  xFormat,
  height = 240,
}: {
  data: Record<string, unknown>[];
  xKey: string;
  series: { key: string; label: string; color: string }[];
  yDomain?: [number, number];
  reference?: { value: number; label: string };
  unit?: string;
  xFormat?: (value: string) => string;
  height?: number;
}) {
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -12 }}>
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis dataKey={xKey} {...AXIS} tickFormatter={xFormat} minTickGap={24} />
          <YAxis {...AXIS} axisLine={false} domain={yDomain ?? ["auto", "auto"]} allowDecimals />
          {reference && (
            <ReferenceLine y={reference.value} stroke="var(--axis-text)" strokeWidth={1} label={{ value: reference.label, position: "insideTopRight", fill: "var(--axis-text)", fontSize: 11 }} />
          )}
          <Tooltip content={<ChartTooltip unit={unit} labelFormat={xFormat} />} cursor={{ stroke: "var(--grid)", strokeWidth: 1 }} />
          {series.map((s) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={s.color}
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              dot={false}
              activeDot={{ r: 5, strokeWidth: 2, stroke: "var(--card)", fill: s.color }}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function AreaTrendChart({ data, xKey, series, xFormat, unit, height = 220 }: { data: Record<string, unknown>[]; xKey: string; series: { key: string; label: string; color: string }[]; xFormat?: (value: string) => string; unit?: string; height?: number }) {
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -12 }}>
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis dataKey={xKey} {...AXIS} tickFormatter={xFormat} minTickGap={24} />
          <YAxis {...AXIS} axisLine={false} allowDecimals={false} />
          <Tooltip content={<ChartTooltip unit={unit} labelFormat={xFormat} />} cursor={{ stroke: "var(--grid)", strokeWidth: 1 }} />
          {series.map((s) => (
            <Area
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={s.color}
              strokeWidth={2}
              fill={s.color}
              fillOpacity={0.1}
              activeDot={{ r: 5, strokeWidth: 2, stroke: "var(--card)", fill: s.color }}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ColumnChart({
  data,
  xKey,
  yKey,
  label,
  color = "var(--series-1)",
  unit,
  xFormat,
  reference,
  height = 200,
}: {
  data: Record<string, unknown>[];
  xKey: string;
  yKey: string;
  label: string;
  color?: string;
  unit?: string;
  xFormat?: (value: string) => string;
  reference?: { value: number; label: string };
  height?: number;
}) {
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }} barCategoryGap="30%">
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis dataKey={xKey} {...AXIS} tickFormatter={xFormat} minTickGap={8} />
          <YAxis {...AXIS} axisLine={false} allowDecimals={false} />
          {reference && (
            <ReferenceLine y={reference.value} stroke="var(--axis-text)" strokeWidth={1} label={{ value: reference.label, position: "insideTopRight", fill: "var(--axis-text)", fontSize: 11 }} />
          )}
          <Tooltip content={<ChartTooltip unit={unit} labelFormat={xFormat} />} cursor={{ fill: "var(--muted)" }} />
          <Bar dataKey={yKey} name={label} fill={color} radius={[4, 4, 0, 0]} maxBarSize={24} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Horizontal score bars with a target marker - clearer than a radar for comparing a few skills. */
export function SkillBars({ rows }: { rows: { label: string; score: number | null; target?: number; color?: string }[] }) {
  return (
    <ul className="space-y-3">
      {rows.map((row) => (
        <li key={row.label} className="space-y-1">
          <div className="flex justify-between text-sm">
            <span>{row.label}</span>
            <span className="tabular-nums text-muted-foreground">{row.score === null ? "No data yet" : `${Math.round(row.score)}/100`}</span>
          </div>
          <div className="relative h-2.5 rounded-full bg-muted">
            <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${row.score ?? 0}%`, background: row.color ?? "var(--series-1)" }} />
            {row.target !== undefined && (
              <div className="absolute -top-1 h-4.5 w-0.5 rounded bg-foreground/60" style={{ left: `${row.target}%` }} title={`Target ${Math.round(row.target)}`} aria-hidden />
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Calendar heatmap of study minutes (sequential single-hue ramp). */
export function CalendarHeatmap({ days }: { days: { day: string; minutes: number }[] }) {
  if (!days.length) return null;
  const max = Math.max(...days.map((d) => d.minutes), 1);
  const level = (m: number) => (m <= 0 ? 0 : Math.min(5, Math.ceil((m / max) * 5)));
  const first = new Date(`${days[0].day}T00:00:00`);
  const offset = (first.getDay() + 6) % 7; // Monday-first grid
  const cells: ({ day: string; minutes: number } | null)[] = [...Array(offset).fill(null), ...days];
  const weeks: (typeof cells)[] = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
  return (
    <div>
      <div className="flex gap-1 overflow-x-auto pb-1">
        {weeks.map((week, wi) => (
          <div key={wi} className="flex flex-col gap-1">
            {week.map((cell, di) =>
              cell ? (
                <div
                  key={cell.day}
                  className="size-3.5 rounded-[3px]"
                  style={{ background: `var(--seq-${level(cell.minutes)})` }}
                  title={`${shortDay(cell.day)}: ${cell.minutes} min`}
                  aria-label={`${shortDay(cell.day)}: ${cell.minutes} minutes`}
                />
              ) : (
                <div key={`pad-${di}`} className="size-3.5" />
              ),
            )}
          </div>
        ))}
      </div>
      <div className="mt-2 flex items-center gap-1 text-xs text-muted-foreground" aria-hidden>
        Less {[0, 1, 2, 3, 4, 5].map((l) => <span key={l} className="size-3 rounded-[3px]" style={{ background: `var(--seq-${l})` }} />)} More
      </div>
    </div>
  );
}

/** Category x week heatmap of mistake counts. */
export function MatrixHeatmap({ columns, rows }: { columns: string[]; rows: { label: string; values: number[] }[] }) {
  const max = Math.max(1, ...rows.flatMap((r) => r.values));
  return (
    <div className="overflow-x-auto">
      <table className="text-xs">
        <thead>
          <tr>
            <th />
            {columns.map((c) => (
              <th key={c} className="px-1 pb-1 font-normal text-muted-foreground">
                {shortWeek(c)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <th className="whitespace-nowrap pr-2 text-left font-normal text-muted-foreground">{row.label}</th>
              {row.values.map((v, i) => (
                <td key={i} className="p-0.5">
                  <div
                    className="grid size-7 place-items-center rounded-md tabular-nums"
                    style={{ background: `var(--seq-${v ? Math.min(5, Math.ceil((v / max) * 5)) : 0})`, color: v / max > 0.6 ? "white" : "var(--foreground)" }}
                    title={`${row.label}, ${columns[i]}: ${v}`}
                  >
                    {v || ""}
                  </div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
