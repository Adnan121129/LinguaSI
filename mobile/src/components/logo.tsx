import { View } from "react-native";
import Svg, { Defs, LinearGradient, Rect, Stop, Text as SvgText } from "react-native-svg";

import { Text } from "@/components/ui";
import { useTheme } from "@/lib/theme";

export function LogoMark({ size = 36 }: { size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 64 64" accessibilityLabel="LinguaSI">
      <Defs>
        <LinearGradient id="lsi" x1="0" y1="0" x2="1" y2="1">
          <Stop offset="0" stopColor="#6366f1" />
          <Stop offset="1" stopColor="#0ea5e9" />
        </LinearGradient>
      </Defs>
      <Rect width={64} height={64} rx={16} fill="url(#lsi)" />
      <SvgText x={32} y={42} textAnchor="middle" fontSize={28} fontWeight="700" fill="#ffffff">
        Li
      </SvgText>
    </Svg>
  );
}

export function Logo({ size = 36 }: { size?: number }) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
      <LogoMark size={size} />
      <Text style={{ fontSize: size * 0.55, fontWeight: "700" }}>
        Lingua<Text style={{ fontSize: size * 0.55, fontWeight: "700", color: colors.primary }}>SI</Text>
      </Text>
    </View>
  );
}
