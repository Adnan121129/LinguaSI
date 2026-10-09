import { AlertTriangle, ChevronRight, Inbox, RefreshCw, type LucideIcon } from "lucide-react-native";
import { Children, forwardRef, type ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  Text as RNText,
  TextInput,
  View,
  type StyleProp,
  type TextInputProps,
  type TextProps,
  type TextStyle,
  type ViewProps,
  type ViewStyle,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { errorMessage } from "@/lib/api";
import { useTheme, type Colors } from "@/lib/theme";

export type Tone = "default" | "muted" | "primary" | "accent" | "success" | "warning" | "danger";

export function toneColors(colors: Colors, tone: Tone): { fg: string; bg: string } {
  switch (tone) {
    case "primary":
      return { fg: colors.primary, bg: colors.primarySoft };
    case "accent":
      return { fg: colors.accent, bg: colors.accentSoft };
    case "success":
      return { fg: colors.success, bg: colors.successSoft };
    case "warning":
      return { fg: colors.warning, bg: colors.warningSoft };
    case "danger":
      return { fg: colors.danger, bg: colors.dangerSoft };
    case "muted":
      return { fg: colors.mutedForeground, bg: colors.muted };
    default:
      return { fg: colors.foreground, bg: colors.muted };
  }
}

// --- Text ------------------------------------------------------------------------------------------

const VARIANTS: Record<string, TextStyle> = {
  display: { fontSize: 34, fontWeight: "700", letterSpacing: -0.5 },
  title: { fontSize: 26, fontWeight: "700", letterSpacing: -0.3 },
  heading: { fontSize: 18, fontWeight: "600" },
  subheading: { fontSize: 16, fontWeight: "600" },
  body: { fontSize: 15, lineHeight: 22 },
  small: { fontSize: 13, lineHeight: 18 },
  caption: { fontSize: 12, lineHeight: 16 },
  label: { fontSize: 11, fontWeight: "600", letterSpacing: 0.6, textTransform: "uppercase" },
};

type TextVariant = keyof typeof VARIANTS;

export function Text({ variant = "body", tone = "default", weight, style, ...props }: TextProps & { variant?: TextVariant; tone?: Tone; weight?: TextStyle["fontWeight"] }) {
  const { colors } = useTheme();
  const color = tone === "default" ? colors.foreground : tone === "muted" ? colors.mutedForeground : toneColors(colors, tone).fg;
  return <RNText {...props} style={[VARIANTS[variant], { color }, weight ? { fontWeight: weight } : null, style]} />;
}

// --- Layout ----------------------------------------------------------------------------------------

/**
 * Standard screen: scrolls, pads content and supports pull-to-refresh. Tab screens set `safeTop`
 * (they have no navigation header); stack screens get the native header with a back button.
 */
export function Screen({
  children,
  scroll = true,
  safeTop = false,
  refreshing,
  onRefresh,
  contentStyle,
}: {
  children: ReactNode;
  scroll?: boolean;
  safeTop?: boolean;
  refreshing?: boolean;
  onRefresh?: () => void;
  contentStyle?: StyleProp<ViewStyle>;
}) {
  const { colors } = useTheme();
  const body = scroll ? (
    <ScrollView
      contentContainerStyle={[{ padding: 16, paddingBottom: 40, gap: 16 }, contentStyle]}
      keyboardShouldPersistTaps="handled"
      refreshControl={onRefresh ? <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} tintColor={colors.primary} colors={[colors.primary]} /> : undefined}
    >
      {children}
    </ScrollView>
  ) : (
    <View style={[{ flex: 1 }, contentStyle]}>{children}</View>
  );
  return (
    <SafeAreaView edges={safeTop ? ["top", "left", "right"] : ["left", "right"]} style={{ flex: 1, backgroundColor: colors.background }}>
      {body}
    </SafeAreaView>
  );
}

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <View style={{ flexDirection: "row", alignItems: "flex-start", gap: 12 }}>
      <View style={{ flex: 1, gap: 4 }}>
        <Text variant="title">{title}</Text>
        {subtitle ? <Text tone="muted">{subtitle}</Text> : null}
      </View>
      {action}
    </View>
  );
}

export function Card({ children, style, onPress, tone }: { children: ReactNode; style?: StyleProp<ViewStyle>; onPress?: () => void; tone?: Tone }) {
  const { colors } = useTheme();
  const tinted = tone && tone !== "default" ? toneColors(colors, tone) : null;
  const base: ViewStyle = {
    backgroundColor: tinted ? tinted.bg : colors.card,
    borderColor: tinted ? tinted.bg : colors.border,
    borderWidth: 1,
    borderRadius: 18,
    padding: 16,
    gap: 10,
  };
  if (!onPress) return <View style={[base, style]}>{children}</View>;
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [base, { opacity: pressed ? 0.85 : 1 }, style]} accessibilityRole="button">
      {children}
    </Pressable>
  );
}

export function CardHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
      <View style={{ flex: 1, gap: 2 }}>
        <Text variant="subheading">{title}</Text>
        {subtitle ? <Text variant="small" tone="muted">{subtitle}</Text> : null}
      </View>
      {action}
    </View>
  );
}

export function Row({ children, gap = 8, style, wrap, ...props }: ViewProps & { gap?: number; wrap?: boolean }) {
  return (
    <View {...props} style={[{ flexDirection: "row", alignItems: "center", gap, flexWrap: wrap ? "wrap" : "nowrap" }, style]}>
      {children}
    </View>
  );
}

export function Divider() {
  const { colors } = useTheme();
  return <View style={{ height: 1, backgroundColor: colors.border }} />;
}

// --- Controls --------------------------------------------------------------------------------------

type ButtonVariant = "primary" | "secondary" | "outline" | "ghost" | "danger";

export function Button({
  title,
  onPress,
  variant = "primary",
  size = "md",
  loading,
  disabled,
  icon: Icon,
  style,
  accessibilityLabel,
}: {
  title: string;
  onPress?: () => void;
  variant?: ButtonVariant;
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  disabled?: boolean;
  icon?: LucideIcon;
  style?: StyleProp<ViewStyle>;
  accessibilityLabel?: string;
}) {
  const { colors } = useTheme();
  const palette: Record<ButtonVariant, { bg: string; fg: string; border: string }> = {
    primary: { bg: colors.primary, fg: colors.primaryForeground, border: colors.primary },
    secondary: { bg: colors.primarySoft, fg: colors.primary, border: colors.primarySoft },
    outline: { bg: colors.card, fg: colors.foreground, border: colors.border },
    ghost: { bg: "transparent", fg: colors.mutedForeground, border: "transparent" },
    danger: { bg: colors.danger, fg: "#ffffff", border: colors.danger },
  };
  const p = palette[variant];
  const height = size === "sm" ? 36 : size === "lg" ? 52 : 44;
  const inactive = disabled || loading;
  return (
    <Pressable
      onPress={onPress}
      disabled={inactive}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? title}
      accessibilityState={{ disabled: !!inactive, busy: !!loading }}
      style={({ pressed }) => [
        {
          height,
          paddingHorizontal: size === "sm" ? 12 : 18,
          borderRadius: 14,
          borderWidth: 1,
          borderColor: p.border,
          backgroundColor: p.bg,
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          opacity: inactive ? 0.55 : pressed ? 0.85 : 1,
        },
        style,
      ]}
    >
      {loading ? <ActivityIndicator size="small" color={p.fg} /> : Icon ? <Icon size={size === "sm" ? 15 : 18} color={p.fg} /> : null}
      <RNText style={{ color: p.fg, fontSize: size === "lg" ? 16 : size === "sm" ? 13 : 15, fontWeight: "600" }}>{title}</RNText>
    </Pressable>
  );
}

export const Input = forwardRef<TextInput, TextInputProps & { label?: string; hint?: string; error?: string }>(function Input({ label, hint, error, style, multiline, ...props }, ref) {
  const { colors } = useTheme();
  return (
    <View style={{ gap: 6 }}>
      {label ? <Text variant="small" weight="600">{label}</Text> : null}
      <TextInput
        ref={ref}
        placeholderTextColor={colors.mutedForeground}
        multiline={multiline}
        accessibilityLabel={props.accessibilityLabel ?? label}
        {...props}
        style={[
          {
            minHeight: multiline ? 96 : 46,
            borderWidth: 1,
            borderColor: error ? colors.danger : colors.border,
            backgroundColor: colors.card,
            color: colors.foreground,
            borderRadius: 12,
            paddingHorizontal: 14,
            paddingVertical: multiline ? 12 : 10,
            fontSize: 15,
            textAlignVertical: multiline ? "top" : "center",
          },
          style,
        ]}
      />
      {error ? <Text variant="caption" tone="danger">{error}</Text> : hint ? <Text variant="caption" tone="muted">{hint}</Text> : null}
    </View>
  );
});

export function Chip({ label, selected, onPress }: { label: string; selected?: boolean; onPress?: () => void }) {
  const { colors } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected: !!selected }}
      style={{
        paddingHorizontal: 12,
        paddingVertical: 7,
        borderRadius: 999,
        borderWidth: 1,
        borderColor: selected ? colors.primary : colors.border,
        backgroundColor: selected ? colors.primarySoft : colors.card,
      }}
    >
      <RNText style={{ color: selected ? colors.primary : colors.mutedForeground, fontSize: 13, fontWeight: "500" }}>{label}</RNText>
    </Pressable>
  );
}

export function Segmented<T extends string>({ value, onChange, options }: { value: T; onChange: (value: T) => void; options: { value: T; label: string }[] }) {
  const { colors } = useTheme();
  return (
    <View accessibilityRole="tablist" style={{ flexDirection: "row", backgroundColor: colors.muted, borderRadius: 12, padding: 3, gap: 3 }}>
      {options.map((option) => {
        const active = option.value === value;
        return (
          <Pressable
            key={option.value}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
            onPress={() => onChange(option.value)}
            style={{ flex: 1, paddingVertical: 8, borderRadius: 9, alignItems: "center", backgroundColor: active ? colors.card : "transparent" }}
          >
            <RNText style={{ fontSize: 13, fontWeight: "600", color: active ? colors.foreground : colors.mutedForeground }}>{option.label}</RNText>
          </Pressable>
        );
      })}
    </View>
  );
}

/** Single-choice list (radio group) used by quizzes, practice and comprehension questions. */
export function ChoiceList({
  options,
  value,
  onChange,
  correct,
  disabled,
}: {
  options: string[];
  value: string | undefined;
  onChange: (value: string) => void;
  correct?: string | null;
  disabled?: boolean;
}) {
  const { colors } = useTheme();
  const revealed = correct !== undefined && correct !== null;
  return (
    <View accessibilityRole="radiogroup" style={{ gap: 8 }}>
      {options.map((option) => {
        const selected = value === option;
        const isCorrect = revealed && option.trim().toLowerCase() === correct!.trim().toLowerCase();
        const border = revealed && isCorrect ? colors.success : revealed && selected ? colors.danger : selected ? colors.primary : colors.border;
        const bg = revealed && isCorrect ? colors.successSoft : revealed && selected ? colors.dangerSoft : selected ? colors.primarySoft : colors.card;
        return (
          <Pressable
            key={option}
            onPress={() => onChange(option)}
            disabled={disabled}
            accessibilityRole="radio"
            accessibilityState={{ checked: selected, disabled: !!disabled }}
            accessibilityLabel={option}
            style={{ flexDirection: "row", alignItems: "center", gap: 12, borderWidth: 1, borderColor: border, backgroundColor: bg, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12 }}
          >
            <View style={{ width: 18, height: 18, borderRadius: 9, borderWidth: 2, borderColor: selected ? colors.primary : colors.border, alignItems: "center", justifyContent: "center" }}>
              {selected ? <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: colors.primary }} /> : null}
            </View>
            <Text style={{ flex: 1 }}>{option}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

// --- Display ---------------------------------------------------------------------------------------

export function Badge({ label, tone = "muted" }: { label: string; tone?: Tone }) {
  const { colors } = useTheme();
  const t = toneColors(colors, tone);
  return (
    <View style={{ alignSelf: "flex-start", backgroundColor: t.bg, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 3 }}>
      <RNText style={{ color: t.fg, fontSize: 11, fontWeight: "600" }}>{label}</RNText>
    </View>
  );
}

export function ProgressBar({ value, tone = "primary", height = 8, label }: { value: number; tone?: Tone; height?: number; label?: string }) {
  const { colors } = useTheme();
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <View
      accessibilityRole="progressbar"
      accessibilityLabel={label}
      accessibilityValue={{ min: 0, max: 100, now: Math.round(clamped) }}
      style={{ height, borderRadius: height, backgroundColor: colors.muted, overflow: "hidden" }}
    >
      <View style={{ width: `${clamped}%`, height: "100%", borderRadius: height, backgroundColor: toneColors(colors, tone).fg }} />
    </View>
  );
}

/** Strings and numbers (including mixed `text {value} text` children) must be inside <Text> on native. */
function isTextContent(children: ReactNode) {
  const parts = Children.toArray(children);
  return parts.length > 0 && parts.every((part) => typeof part === "string" || typeof part === "number");
}

export function Notice({ tone = "primary", icon: Icon, children }: { tone?: Tone; icon?: LucideIcon; children: ReactNode }) {
  const { colors } = useTheme();
  const t = toneColors(colors, tone);
  return (
    <View style={{ flexDirection: "row", gap: 10, backgroundColor: t.bg, borderRadius: 14, padding: 12, alignItems: "flex-start" }}>
      {Icon ? <Icon size={16} color={t.fg} style={{ marginTop: 2 }} /> : null}
      <View style={{ flex: 1 }}>{isTextContent(children) ? <Text variant="small">{children}</Text> : children}</View>
    </View>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <View style={{ gap: 2, minWidth: 90 }}>
      <Text variant="label" tone="muted">{label}</Text>
      {typeof value === "string" || typeof value === "number" ? <Text variant="heading">{value}</Text> : value}
      {hint ? <Text variant="caption" tone="muted">{hint}</Text> : null}
    </View>
  );
}

/** Stats laid out in equal columns that wrap on narrow screens, so labels are never clipped. */
export function StatGrid({ children, columns = 2 }: { children: ReactNode; columns?: number }) {
  return (
    <View style={{ flexDirection: "row", flexWrap: "wrap", rowGap: 14 }}>
      {Children.toArray(children).map((child, i) => (
        <View key={i} style={{ width: `${100 / columns}%`, paddingRight: 8 }}>
          {child}
        </View>
      ))}
    </View>
  );
}

/** A tappable row with an icon, used for menus and lists. */
export function ListRow({ icon: Icon, title, subtitle, right, onPress, tone = "primary" }: { icon?: LucideIcon; title: string; subtitle?: string; right?: ReactNode; onPress?: () => void; tone?: Tone }) {
  const { colors } = useTheme();
  const t = toneColors(colors, tone);
  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress}
      accessibilityRole={onPress ? "button" : undefined}
      style={({ pressed }) => ({ flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 12, opacity: pressed ? 0.7 : 1 })}
    >
      {Icon ? (
        <View style={{ width: 38, height: 38, borderRadius: 12, backgroundColor: t.bg, alignItems: "center", justifyContent: "center" }}>
          <Icon size={19} color={t.fg} />
        </View>
      ) : null}
      <View style={{ flex: 1, gap: 2 }}>
        <Text weight="600">{title}</Text>
        {subtitle ? <Text variant="small" tone="muted" numberOfLines={2}>{subtitle}</Text> : null}
      </View>
      {right}
      {onPress ? <ChevronRight size={18} color={colors.mutedForeground} /> : null}
    </Pressable>
  );
}

export function Loading({ label }: { label?: string }) {
  const { colors } = useTheme();
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center", gap: 12, padding: 32, backgroundColor: colors.background }}>
      <ActivityIndicator size="large" color={colors.primary} />
      {label ? <Text tone="muted">{label}</Text> : null}
    </View>
  );
}

export function ErrorState({ error, onRetry, title = "Something went wrong" }: { error: unknown; onRetry?: () => void; title?: string }) {
  const { colors } = useTheme();
  return (
    <View accessibilityRole="alert" style={{ gap: 10, borderRadius: 16, borderWidth: 1, borderColor: colors.dangerSoft, backgroundColor: colors.dangerSoft, padding: 16 }}>
      <Row>
        <AlertTriangle size={16} color={colors.danger} />
        <Text weight="600" tone="danger">{title}</Text>
      </Row>
      <Text variant="small">{errorMessage(error)}</Text>
      {onRetry ? <Button title="Try again" icon={RefreshCw} variant="outline" size="sm" onPress={onRetry} style={{ alignSelf: "flex-start" }} /> : null}
    </View>
  );
}

export function EmptyState({ title, description, icon: Icon = Inbox, action }: { title: string; description?: string; icon?: LucideIcon; action?: ReactNode }) {
  const { colors } = useTheme();
  return (
    <View style={{ alignItems: "center", gap: 10, padding: 24, borderRadius: 18, borderWidth: 1, borderStyle: "dashed", borderColor: colors.border }}>
      <View style={{ backgroundColor: colors.muted, borderRadius: 999, padding: 12 }}>
        <Icon size={20} color={colors.mutedForeground} />
      </View>
      <Text weight="600" style={{ textAlign: "center" }}>{title}</Text>
      {description ? <Text variant="small" tone="muted" style={{ textAlign: "center" }}>{description}</Text> : null}
      {action}
    </View>
  );
}

/** Query states in one place: spinner while loading, an error card with retry, otherwise the content. */
export function QueryView<T>({ query, children, loadingLabel }: { query: { data: T | undefined; error: unknown; isLoading: boolean; refetch: () => unknown }; children: (data: T) => ReactNode; loadingLabel?: string }) {
  if (query.isLoading) return <Loading label={loadingLabel} />;
  if (query.error || query.data === undefined)
    return (
      <Screen>
        <ErrorState error={query.error} onRetry={() => query.refetch()} />
      </Screen>
    );
  return <>{children(query.data)}</>;
}
