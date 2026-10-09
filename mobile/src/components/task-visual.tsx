import { ArrowDown } from "lucide-react-native";
import { useState } from "react";
import { View, type LayoutChangeEvent } from "react-native";
import Svg, { Line, Path, Text as SvgText } from "react-native-svg";

import { LineChart } from "@/components/charts";
import { Card, Row, Text } from "@/components/ui";
import { useTheme } from "@/lib/theme";
import type { ChartVisual } from "@/lib/types";

function Legend({ items }: { items: { label: string; color: string }[] }) {
  if (items.length < 2) return null;
  return (
    <Row wrap gap={12}>
      {items.map((item) => (
        <Row key={item.label} gap={6}>
          <View style={{ width: 10, height: 10, borderRadius: 3, backgroundColor: item.color }} />
          <Text variant="caption" tone="muted">{item.label}</Text>
        </Row>
      ))}
    </Row>
  );
}

/** Categories on the x axis, one bar per series (fixed colour order), 2px gaps and rounded data ends. */
function GroupedBars({ categories, series }: { categories: string[]; series: { name: string; values: number[] }[] }) {
  const { colors } = useTheme();
  const [width, setWidth] = useState(0);
  const height = 220;
  const top = 10;
  const bottom = 34;
  const left = 32;
  const max = Math.max(1, ...series.flatMap((s) => s.values)) * 1.1;
  const plotH = height - top - bottom;
  const slot = categories.length ? (width - left) / categories.length : 0;
  const barW = Math.max(4, Math.min(24, (slot * 0.75 - 2 * (series.length - 1)) / Math.max(1, series.length)));
  const group = barW * series.length + 2 * (series.length - 1);
  const y = (v: number) => top + plotH - (v / max) * plotH;
  return (
    <View onLayout={(e: LayoutChangeEvent) => setWidth(Math.round(e.nativeEvent.layout.width))}>
      {width ? (
        <Svg width={width} height={height}>
          {[0, 0.5, 1].map((f) => (
            <Line key={f} x1={left} x2={width} y1={y(max * f)} y2={y(max * f)} stroke={colors.grid} strokeWidth={1} />
          ))}
          {[0, 0.5, 1].map((f) => (
            <SvgText key={`t${f}`} x={left - 4} y={y(max * f) + 4} fontSize={10} fill={colors.axisText} textAnchor="end">
              {Math.round(max * f)}
            </SvgText>
          ))}
          {categories.map((category, ci) =>
            series.map((s, si) => {
              const v = s.values[ci] ?? 0;
              const x = left + slot * ci + (slot - group) / 2 + si * (barW + 2);
              const h = Math.max(0, (v / max) * plotH);
              const r = Math.min(4, h / 2, barW / 2);
              const base = top + plotH;
              const d = h > 0 ? `M${x},${base} L${x},${base - h + r} Q${x},${base - h} ${x + r},${base - h} L${x + barW - r},${base - h} Q${x + barW},${base - h} ${x + barW},${base - h + r} L${x + barW},${base} Z` : "";
              return <Path key={`${ci}-${si}`} d={d} fill={colors.series[si % colors.series.length]} />;
            }),
          )}
          {categories.map((category, ci) => (
            <SvgText key={category} x={left + slot * ci + slot / 2} y={height - 18} fontSize={10} fill={colors.axisText} textAnchor="middle">
              {category.length > Math.floor(slot / 6) ? `${category.slice(0, Math.max(3, Math.floor(slot / 6) - 1))}…` : category}
            </SvgText>
          ))}
        </Svg>
      ) : (
        <View style={{ height }} />
      )}
    </View>
  );
}

function Pie({ values, size = 150 }: { values: number[]; size?: number }) {
  const { colors } = useTheme();
  const total = values.reduce((a, b) => a + b, 0) || 1;
  const r = size / 2 - 2;
  const c = size / 2;
  // Start angle of each slice: cumulative share of the total, starting at 12 o'clock.
  const starts = values.map((_, i) => -Math.PI / 2 + (values.slice(0, i).reduce((a, b) => a + b, 0) / total) * Math.PI * 2);
  return (
    <Svg width={size} height={size}>
      {values.map((v, i) => {
        const sweep = (v / total) * Math.PI * 2;
        const x1 = c + r * Math.cos(starts[i]);
        const y1 = c + r * Math.sin(starts[i]);
        const x2 = c + r * Math.cos(starts[i] + sweep);
        const y2 = c + r * Math.sin(starts[i] + sweep);
        const large = sweep > Math.PI ? 1 : 0;
        const d = values.length === 1 ? `M${c - r},${c} a${r},${r} 0 1,0 ${2 * r},0 a${r},${r} 0 1,0 ${-2 * r},0` : `M${c},${c} L${x1},${y1} A${r},${r} 0 ${large} 1 ${x2},${y2} Z`;
        return <Path key={i} d={d} fill={colors.series[i % colors.series.length]} stroke={colors.card} strokeWidth={2} />;
      })}
    </Svg>
  );
}

/** The chart, table or process diagram that an IELTS-style Task 1 asks the learner to describe. */
export function TaskVisual({ visual }: { visual: ChartVisual }) {
  const { colors } = useTheme();
  const categories = visual.categories ?? [];
  const series = visual.series ?? [];
  const legend = series.map((s, i) => ({ label: s.name, color: colors.series[i % colors.series.length] }));
  let body: React.ReactNode = null;

  if (visual.chart_type === "line") {
    const rows = categories.map((category, i) => ({ category, ...Object.fromEntries(series.map((s) => [s.name, s.values[i]])) }));
    body = (
      <>
        <Legend items={legend} />
        <LineChart data={rows} xKey="category" series={series.map((s, i) => ({ key: s.name, label: s.name, color: colors.series[i % colors.series.length] }))} />
      </>
    );
  } else if (visual.chart_type === "bar") {
    body = (
      <>
        <Legend items={legend} />
        <GroupedBars categories={categories} series={series} />
      </>
    );
  } else if (visual.chart_type === "pie") {
    body = (
      <>
        <Row wrap gap={16} style={{ justifyContent: "center" }}>
          {series.map((s) => (
            <View key={s.name} style={{ alignItems: "center", gap: 6 }}>
              <Pie values={s.values} />
              <Text variant="small" weight="600">{s.name}</Text>
            </View>
          ))}
        </Row>
        <View style={{ gap: 4 }}>
          {categories.map((category, i) => (
            <Row key={category} gap={8}>
              <View style={{ width: 10, height: 10, borderRadius: 3, backgroundColor: colors.series[i % colors.series.length] }} />
              <Text variant="caption" style={{ flex: 1 }}>{category}</Text>
              <Text variant="caption" tone="muted">{series.map((s) => `${s.values[i]}${visual.unit === "%" ? "%" : ""}`).join(" · ")}</Text>
            </Row>
          ))}
        </View>
      </>
    );
  } else if (visual.chart_type === "table") {
    body = (
      <View style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 12, overflow: "hidden" }}>
        <View style={{ flexDirection: "row", backgroundColor: colors.muted }}>
          <Text variant="caption" style={{ flex: 1.4, padding: 8 }} />
          {series.map((s) => (
            <Text key={s.name} variant="caption" weight="600" style={{ flex: 1, padding: 8, textAlign: "right" }}>{s.name}</Text>
          ))}
        </View>
        {categories.map((category, i) => (
          <View key={category} style={{ flexDirection: "row", borderTopWidth: 1, borderTopColor: colors.border }}>
            <Text variant="small" style={{ flex: 1.4, padding: 8 }}>{category}</Text>
            {series.map((s) => (
              <Text key={s.name} variant="small" style={{ flex: 1, padding: 8, textAlign: "right", fontVariant: ["tabular-nums"] }}>{s.values[i]}</Text>
            ))}
          </View>
        ))}
      </View>
    );
  } else if (visual.chart_type === "process") {
    body = (
      <View style={{ gap: 2, alignItems: "center" }}>
        {(visual.steps ?? []).map((step, i, all) => (
          <View key={step} style={{ width: "100%", alignItems: "center" }}>
            <View style={{ width: "100%", borderWidth: 1, borderColor: colors.border, backgroundColor: colors.muted, borderRadius: 12, padding: 10, flexDirection: "row", gap: 8 }}>
              <Text weight="700" tone="primary">{i + 1}</Text>
              <Text variant="small" style={{ flex: 1 }}>{step}</Text>
            </View>
            {i < all.length - 1 ? <ArrowDown size={16} color={colors.mutedForeground} style={{ marginVertical: 2 }} /> : null}
          </View>
        ))}
      </View>
    );
  }

  return (
    <Card>
      <Text weight="600">
        {visual.title}
        {visual.unit && visual.chart_type !== "process" ? <Text variant="small" tone="muted"> · {visual.unit}</Text> : null}
      </Text>
      {body}
    </Card>
  );
}
