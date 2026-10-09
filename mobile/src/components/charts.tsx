import { Table2 } from "lucide-react-native";
import { useState, type ReactNode } from "react";
import { Pressable, ScrollView, View, type LayoutChangeEvent } from "react-native";
import Svg, { Circle, Line, Path, Text as SvgText } from "react-native-svg";

import { Card, Row, Text } from "@/components/ui";
import { useTheme } from "@/lib/theme";

// Chart rules shared with the web app: the title is the question the chart answers, every chart has
// a table view, a legend appears only for two or more series, one series uses one hue, colour
// follows the entity (fixed order), lines are 2px, bars have 4px rounded data ends, and values can
// be inspected by tapping (the touch equivalent of a hover tooltip).

export type Column = { key: string; label: string; format?: (value: unknown) => string };

function formatCell(column: Column, value: unknown) {
  if (column.format) return column.format(value);
  return value === null || value === undefined ? "—" : String(value);
}

export function ChartCard({
  question,
  description,
  children,
  rows,
  columns,
  legend,
}: {
  question: string;
  description?: string;
  children: ReactNode;
  rows: Record<string, unknown>[];
  columns: Column[];
  legend?: { label: string; color: string }[];
}) {
  const { colors } = useTheme();
  const [table, setTable] = useState(false);
  return (
    <Card>
      <Row style={{ alignItems: "flex-start" }}>
        <View style={{ flex: 1, gap: 2 }}>
          <Text variant="subheading" accessibilityRole="header">{question}</Text>
          {description ? <Text variant="small" tone="muted">{description}</Text> : null}
        </View>
        <Pressable onPress={() => setTable((t) => !t)} accessibilityRole="button" accessibilityState={{ selected: table }} hitSlop={8} style={{ flexDirection: "row", alignItems: "center", gap: 4, paddingVertical: 4 }}>
          <Table2 size={14} color={colors.mutedForeground} />
          <Text variant="caption" tone="muted">{table ? "Chart" : "Table"}</Text>
        </Pressable>
      </Row>
      {legend && legend.length > 1 && !table ? (
        <Row wrap gap={12} accessibilityLabel="Legend">
          {legend.map((item) => (
            <Row key={item.label} gap={6}>
              <View style={{ width: 14, height: 3, borderRadius: 2, backgroundColor: item.color }} />
              <Text variant="caption" tone="muted">{item.label}</Text>
            </Row>
          ))}
        </Row>
      ) : null}
      {table ? (
        <View style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 12, overflow: "hidden" }}>
          <View style={{ flexDirection: "row", backgroundColor: colors.muted }}>
            {columns.map((c) => (
              <Text key={c.key} variant="label" tone="muted" style={{ flex: 1, paddingHorizontal: 8, paddingVertical: 6 }}>
                {c.label}
              </Text>
            ))}
          </View>
          {rows.map((row, i) => (
            <View key={i} style={{ flexDirection: "row", borderTopWidth: 1, borderTopColor: colors.border }}>
              {columns.map((c) => (
                <Text key={c.key} variant="small" style={{ flex: 1, paddingHorizontal: 8, paddingVertical: 6, fontVariant: ["tabular-nums"] }}>
                  {formatCell(c, row[c.key])}
                </Text>
              ))}
            </View>
          ))}
        </View>
      ) : (
        children
      )}
    </Card>
  );
}

function useWidth(): [number, (e: LayoutChangeEvent) => void] {
  const [width, setWidth] = useState(0);
  return [width, (e) => setWidth(Math.round(e.nativeEvent.layout.width))];
}

function truncate(label: string, max: number) {
  return label.length > max ? `${label.slice(0, Math.max(1, max - 1))}…` : label;
}

function niceMax(value: number) {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const steps = [1, 2, 4, 5, 6, 8, 10]; // even steps, so the mid gridline is a whole number
  return (steps.find((s) => s * magnitude >= value) ?? 10) * magnitude;
}

/** Vertical bars for one series (e.g. study minutes per day), with an optional goal line. */
export function ColumnChart({
  data,
  xKey,
  yKey,
  unit = "",
  reference,
  height = 160,
  label,
  xFormat = (v: string) => v,
}: {
  data: Record<string, unknown>[];
  xKey: string;
  yKey: string;
  unit?: string;
  reference?: number;
  height?: number;
  label: string;
  xFormat?: (v: string) => string;
}) {
  const { colors } = useTheme();
  const [width, onLayout] = useWidth();
  const [selected, setSelected] = useState<number | null>(null);
  const values = data.map((d) => Number(d[yKey]) || 0);
  const max = niceMax(Math.max(...values, reference ?? 0) * 1.1);
  const top = 18;
  const bottom = 20;
  const left = 28;
  const plotH = height - top - bottom;
  const plotW = Math.max(0, width - left);
  const slot = data.length ? plotW / data.length : 0;
  const barW = Math.min(24, slot * 0.6);
  const y = (v: number) => top + plotH - (v / max) * plotH;
  const ticks = [0, max / 2, max];

  const pick = (locationX: number) => {
    const i = Math.floor((locationX - left) / (slot || 1));
    if (i >= 0 && i < data.length) setSelected((s) => (s === i ? null : i));
  };

  return (
    <Pressable onLayout={onLayout} onPress={(e) => pick(e.nativeEvent.locationX)} accessibilityRole="button" accessibilityLabel={`${label} chart. Tap a bar to see its value.`}>
      {width > 0 ? (
        <Svg width={width} height={height} pointerEvents="none">
          {ticks.map((t) => (
            <Line key={t} x1={left} x2={width} y1={y(t)} y2={y(t)} stroke={colors.grid} strokeWidth={1} />
          ))}
          {ticks.map((t) => (
            <SvgText key={`l${t}`} x={left - 6} y={y(t) + 4} fontSize={10} fill={colors.axisText} textAnchor="end">
              {Math.round(t)}
            </SvgText>
          ))}
          {reference ? <Line x1={left} x2={width} y1={y(reference)} y2={y(reference)} stroke={colors.mutedForeground} strokeDasharray="4 4" strokeWidth={1} /> : null}
          {values.map((v, i) => {
            const x = left + slot * i + (slot - barW) / 2;
            const h = Math.max(0, (v / max) * plotH);
            const r = Math.min(4, h / 2, barW / 2);
            const base = top + plotH;
            // Rounded data end (top), square at the baseline.
            const d = h > 0 ? `M${x},${base} L${x},${base - h + r} Q${x},${base - h} ${x + r},${base - h} L${x + barW - r},${base - h} Q${x + barW},${base - h} ${x + barW},${base - h + r} L${x + barW},${base} Z` : "";
            return (
              <Path key={i} d={d} fill={colors.series[0]} opacity={selected === null || selected === i ? 1 : 0.45} />
            );
          })}
          {data.map((d, i) => (
            <SvgText key={`x${i}`} x={left + slot * i + slot / 2} y={height - 4} fontSize={10} fill={colors.axisText} textAnchor="middle">
              {truncate(xFormat(String(d[xKey])), Math.max(3, Math.floor(slot / 6)))}
            </SvgText>
          ))}
          {selected !== null ? (
            <SvgText x={left + slot * selected + slot / 2} y={Math.max(12, y(values[selected]) - 6)} fontSize={11} fontWeight="600" fill={colors.foreground} textAnchor="middle">
              {`${values[selected]}${unit}`}
            </SvgText>
          ) : null}
        </Svg>
      ) : (
        <View style={{ height }} />
      )}
    </Pressable>
  );
}

/** Lines over time (e.g. AI estimated bands). Missing values break the line instead of inventing data. */
export function LineChart({
  data,
  xKey,
  series,
  domain,
  height = 190,
  format = (v: number) => String(v),
  xFormat = (v: string) => v,
  reference,
}: {
  data: Record<string, unknown>[];
  xKey: string;
  series: { key: string; label: string; color: string }[];
  domain?: [number, number];
  height?: number;
  format?: (v: number) => string;
  xFormat?: (v: string) => string;
  reference?: { value: number; label: string };
}) {
  const { colors } = useTheme();
  const [width, onLayout] = useWidth();
  const [selected, setSelected] = useState<number | null>(null);
  const all = data.flatMap((d) => series.map((s) => d[s.key])).filter((v): v is number => typeof v === "number");
  const [min, max] = domain ?? [Math.min(...all, 0), niceMax(Math.max(...all, 1))];
  const top = 12;
  const bottom = 20;
  const left = 28;
  const right = 8;
  const plotH = height - top - bottom;
  const plotW = Math.max(0, width - left - right);
  const x = (i: number) => left + (data.length <= 1 ? plotW / 2 : (plotW * i) / (data.length - 1));
  const y = (v: number) => top + plotH - ((v - min) / (max - min || 1)) * plotH;
  const ticks = [min, (min + max) / 2, max];
  const labelEvery = Math.max(1, Math.ceil(data.length / 5));

  function pathFor(key: string) {
    let d = "";
    let pen = false;
    data.forEach((row, i) => {
      const v = row[key];
      if (typeof v !== "number") {
        pen = false;
        return;
      }
      d += `${pen ? "L" : "M"}${x(i)},${y(v)} `;
      pen = true;
    });
    return d.trim();
  }

  const active = selected !== null ? data[selected] : null;
  const pick = (locationX: number) => {
    if (!data.length) return;
    const i = data.length === 1 ? 0 : Math.round(((locationX - left) / (plotW || 1)) * (data.length - 1));
    const clamped = Math.max(0, Math.min(data.length - 1, i));
    setSelected((s) => (s === clamped ? null : clamped));
  };
  return (
    <View onLayout={onLayout} style={{ gap: 6 }}>
      {active ? (
        <Row wrap gap={10}>
          <Text variant="caption" weight="600">{xFormat(String(active[xKey]))}</Text>
          {series.map((s) => (
            <Row key={s.key} gap={4}>
              <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: s.color }} />
              <Text variant="caption">
                {s.label} {typeof active[s.key] === "number" ? format(active[s.key] as number) : "—"}
              </Text>
            </Row>
          ))}
        </Row>
      ) : (
        <Text variant="caption" tone="muted">Tap the chart to see exact values.</Text>
      )}
      {width > 0 ? (
        <Pressable onPress={(e) => pick(e.nativeEvent.locationX)} accessibilityRole="button" accessibilityLabel="Line chart. Tap to see the values for a day.">
        <Svg width={width} height={height} pointerEvents="none">
          {ticks.map((t) => (
            <Line key={t} x1={left} x2={width - right} y1={y(t)} y2={y(t)} stroke={colors.grid} strokeWidth={1} />
          ))}
          {ticks.map((t) => (
            <SvgText key={`l${t}`} x={left - 6} y={y(t) + 4} fontSize={10} fill={colors.axisText} textAnchor="end">
              {format(t)}
            </SvgText>
          ))}
          {reference ? (
            <>
              <Line x1={left} x2={width - right} y1={y(reference.value)} y2={y(reference.value)} stroke={colors.mutedForeground} strokeWidth={1} strokeDasharray="4 4" />
              <SvgText x={width - right} y={y(reference.value) - 4} fontSize={10} fill={colors.mutedForeground} textAnchor="end">
                {reference.label}
              </SvgText>
            </>
          ) : null}
          {series.map((s) => (
            <Path key={s.key} d={pathFor(s.key)} stroke={s.color} strokeWidth={2} fill="none" strokeLinejoin="round" strokeLinecap="round" />
          ))}
          {series.map((s) =>
            data.map((row, i) =>
              typeof row[s.key] === "number" && (selected === i || data.length <= 12) ? (
                <Circle key={`${s.key}${i}`} cx={x(i)} cy={y(row[s.key] as number)} r={4} fill={s.color} stroke={colors.card} strokeWidth={2} />
              ) : null,
            ),
          )}
          {selected !== null ? <Line x1={x(selected)} x2={x(selected)} y1={top} y2={top + plotH} stroke={colors.mutedForeground} strokeWidth={1} strokeDasharray="3 3" /> : null}
          {data.map((row, i) =>
            i % labelEvery === 0 || i === data.length - 1 ? (
              <SvgText key={`x${i}`} x={x(i)} y={height - 4} fontSize={10} fill={colors.axisText} textAnchor="middle">
                {xFormat(String(row[xKey]))}
              </SvgText>
            ) : null,
          )}
        </Svg>
        </Pressable>
      ) : (
        <View style={{ height }} />
      )}
    </View>
  );
}

/** Labelled horizontal bars in a single hue (e.g. skill scores out of 100). */
export function BarList({ rows, max = 100, format = (v: number) => String(Math.round(v)) }: { rows: { label: string; value: number | null; note?: string; target?: number }[]; max?: number; format?: (v: number) => string }) {
  const { colors } = useTheme();
  return (
    <View style={{ gap: 12 }}>
      {rows.map((row) => (
        <View key={row.label} style={{ gap: 5 }}>
          <Row>
            <Text variant="small" weight="600" style={{ flex: 1 }}>{row.label}</Text>
            <Text variant="small" tone="muted">{row.value === null ? "Not practised yet" : `${format(row.value)}${row.note ? ` · ${row.note}` : ""}`}</Text>
          </Row>
          <View style={{ height: 14, justifyContent: "center" }}>
            <View style={{ height: 8, borderRadius: 4, backgroundColor: colors.muted, overflow: "hidden" }}>
              <View style={{ width: `${Math.max(0, Math.min(100, ((row.value ?? 0) / max) * 100))}%`, height: "100%", borderRadius: 4, backgroundColor: colors.series[0] }} />
            </View>
            {row.target !== undefined ? (
              <View accessibilityLabel={`Target ${format(row.target)}`} style={{ position: "absolute", left: `${Math.min(100, (row.target / max) * 100)}%`, top: 0, width: 2, height: 14, borderRadius: 1, backgroundColor: colors.foreground, opacity: 0.6 }} />
            ) : null}
          </View>
        </View>
      ))}
    </View>
  );
}

/** "2026-10-08" -> "8 Oct". Date-only values are local calendar days, not UTC midnight. */
export const shortDay = (day: string) => new Date(`${day.slice(0, 10)}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
/** "2026-W41" -> "W41". */
export const shortWeek = (week: string) => `W${week.split("-W")[1] ?? week}`;

/** Category x week counts. One sequential hue: darker means more. Tap a cell to read it. */
export function HeatmapGrid({ columns, rows }: { columns: string[]; rows: { label: string; values: number[] }[] }) {
  const { colors } = useTheme();
  const [selected, setSelected] = useState<{ row: string; column: string; value: number } | null>(null);
  const max = Math.max(1, ...rows.flatMap((r) => r.values));
  return (
    <View style={{ gap: 8 }}>
      <Text variant="caption" tone={selected ? "default" : "muted"}>
        {selected ? `${selected.row}, ${shortWeek(selected.column)}: ${selected.value} mistake${selected.value === 1 ? "" : "s"}` : "Tap a cell to see the count."}
      </Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View style={{ gap: 3 }}>
          <View style={{ flexDirection: "row", gap: 3, paddingLeft: 112 }}>
            {columns.map((c) => (
              <Text key={c} variant="caption" tone="muted" style={{ width: 30, textAlign: "center" }}>
                {shortWeek(c)}
              </Text>
            ))}
          </View>
          {rows.map((row) => (
            <View key={row.label} style={{ flexDirection: "row", alignItems: "center", gap: 3 }}>
              <Text variant="caption" tone="muted" numberOfLines={1} style={{ width: 109 }}>
                {row.label}
              </Text>
              {row.values.map((v, i) => {
                const level = v ? Math.min(5, Math.ceil((v / max) * 5)) : 0;
                return (
                  <Pressable
                    key={i}
                    onPress={() => setSelected({ row: row.label, column: columns[i], value: v })}
                    accessibilityRole="button"
                    accessibilityLabel={`${row.label}, ${shortWeek(columns[i])}: ${v}`}
                    style={{ width: 30, height: 30, borderRadius: 6, alignItems: "center", justifyContent: "center", backgroundColor: colors.seq[level] }}
                  >
                    {v ? <Text variant="caption" style={{ color: v / max > 0.6 ? colors.seqInk : colors.foreground, fontVariant: ["tabular-nums"] }}>{v}</Text> : null}
                  </Pressable>
                );
              })}
            </View>
          ))}
        </View>
      </ScrollView>
    </View>
  );
}

/** Study minutes per day as a Monday-first calendar (one sequential hue). Tap a day to read it. */
export function CalendarGrid({ days }: { days: { day: string; minutes: number }[] }) {
  const { colors } = useTheme();
  const [selected, setSelected] = useState<{ day: string; minutes: number } | null>(null);
  if (!days.length) return null;
  const max = Math.max(...days.map((d) => d.minutes), 1);
  const level = (m: number) => (m <= 0 ? 0 : Math.min(5, Math.ceil((m / max) * 5)));
  const first = new Date(`${days[0].day}T00:00:00`);
  const offset = (first.getDay() + 6) % 7;
  const cells: ({ day: string; minutes: number } | null)[] = [...Array(offset).fill(null), ...days];
  const weeks: (typeof cells)[] = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
  return (
    <View style={{ gap: 8 }}>
      <Text variant="caption" tone={selected ? "default" : "muted"}>
        {selected ? `${shortDay(selected.day)}: ${selected.minutes} min` : "Tap a day to see your minutes."}
      </Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View style={{ flexDirection: "row", gap: 4 }}>
          {weeks.map((week, wi) => (
            <View key={wi} style={{ gap: 4 }}>
              {week.map((cell, di) =>
                cell ? (
                  <Pressable
                    key={cell.day}
                    onPress={() => setSelected(cell)}
                    accessibilityRole="button"
                    accessibilityLabel={`${shortDay(cell.day)}: ${cell.minutes} minutes`}
                    style={{ width: 16, height: 16, borderRadius: 4, backgroundColor: colors.seq[level(cell.minutes)] }}
                  />
                ) : (
                  <View key={`pad-${di}`} style={{ width: 16, height: 16 }} />
                ),
              )}
            </View>
          ))}
        </View>
      </ScrollView>
      <Row gap={4}>
        <Text variant="caption" tone="muted">Less</Text>
        {[0, 1, 2, 3, 4, 5].map((l) => (
          <View key={l} style={{ width: 12, height: 12, borderRadius: 3, backgroundColor: colors.seq[l] }} />
        ))}
        <Text variant="caption" tone="muted">More</Text>
      </Row>
    </View>
  );
}
