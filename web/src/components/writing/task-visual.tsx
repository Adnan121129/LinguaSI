"use client";

import { ArrowDown } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { ChartVisual } from "@/lib/types";

const SLOTS = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)", "var(--series-5)"];
const AXIS = { stroke: "var(--grid)", tick: { fill: "var(--axis-text)", fontSize: 12 }, tickLine: false } as const;
const tooltipStyle = { background: "var(--card)", border: "1px solid var(--border)", borderRadius: 12, fontSize: 12, color: "var(--foreground)" };

/** Renders the chart, table or process diagram that an IELTS-style Task 1 asks the learner to describe. */
export function TaskVisual({ visual }: { visual: ChartVisual }) {
  const categories = visual.categories ?? [];
  const series = visual.series ?? [];
  const rows = categories.map((category, i) => ({ category, ...Object.fromEntries(series.map((s) => [s.name, s.values[i]])) }));

  let body: React.ReactNode = null;
  if (visual.chart_type === "line") {
    body = (
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 4, left: -8 }}>
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis dataKey="category" {...AXIS} />
          <YAxis {...AXIS} axisLine={false} label={visual.y_label ? { value: visual.y_label, angle: -90, position: "insideLeft", fill: "var(--axis-text)", fontSize: 11 } : undefined} />
          <Tooltip contentStyle={tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {series.map((s, i) => (
            <Line key={s.name} type="linear" isAnimationActive={false} dataKey={s.name} stroke={SLOTS[i % SLOTS.length]} strokeWidth={2} dot={{ r: 4, strokeWidth: 2, stroke: "var(--card)", fill: SLOTS[i % SLOTS.length] }} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    );
  } else if (visual.chart_type === "bar") {
    body = (
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 4, left: -8 }} barGap={2}>
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis dataKey="category" {...AXIS} interval={0} />
          <YAxis {...AXIS} axisLine={false} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "var(--muted)" }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {series.map((s, i) => (
            <Bar key={s.name} isAnimationActive={false} dataKey={s.name} fill={SLOTS[i % SLOTS.length]} radius={[4, 4, 0, 0]} maxBarSize={24} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  } else if (visual.chart_type === "pie") {
    body = (
      <div className="grid gap-2 sm:grid-cols-2">
        {series.map((s) => (
          <figure key={s.name} className="text-center">
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={categories.map((c, i) => ({ name: c, value: s.values[i] }))}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={0}
                  outerRadius={80}
                  stroke="var(--card)"
                  strokeWidth={2}
                  label={({ value }) => `${value}${visual.unit === "%" ? "%" : ""}`}
                  isAnimationActive={false}
                >
                  {categories.map((c, i) => (
                    <Cell key={c} fill={SLOTS[i % SLOTS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
              </PieChart>
            </ResponsiveContainer>
            <figcaption className="text-sm font-medium">{s.name}</figcaption>
          </figure>
        ))}
        <ul className="col-span-full flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {categories.map((c, i) => (
            <li key={c} className="flex items-center gap-1.5">
              <span className="inline-block size-2.5 rounded-sm" style={{ background: SLOTS[i % SLOTS.length] }} aria-hidden />
              {c}
            </li>
          ))}
        </ul>
      </div>
    );
  } else if (visual.chart_type === "table") {
    body = (
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left">
              <th className="py-2 pr-4 font-medium" />
              {series.map((s) => (
                <th key={s.name} className="py-2 pr-4 text-right font-medium">
                  {s.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {categories.map((c, i) => (
              <tr key={c} className="border-b border-border/60">
                <td className="py-2 pr-4">{c}</td>
                {series.map((s) => (
                  <td key={s.name} className="py-2 pr-4 text-right tabular-nums">
                    {s.values[i]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  } else if (visual.chart_type === "process") {
    body = (
      <ol className="space-y-1">
        {(visual.steps ?? []).map((step, i, all) => (
          <li key={step} className="flex flex-col items-center">
            <div className="w-full rounded-xl border border-border bg-muted/50 px-3 py-2 text-sm">
              <span className="mr-2 font-semibold text-primary">{i + 1}</span>
              {step}
            </div>
            {i < all.length - 1 && <ArrowDown className="my-0.5 size-4 text-muted-foreground" aria-hidden />}
          </li>
        ))}
      </ol>
    );
  }

  return (
    <figure className="rounded-2xl border border-border bg-card p-4">
      <figcaption className="mb-3 text-sm font-semibold">
        {visual.title}
        {visual.unit && visual.chart_type !== "process" && <span className="font-normal text-muted-foreground"> · {visual.unit}</span>}
      </figcaption>
      {body}
    </figure>
  );
}
