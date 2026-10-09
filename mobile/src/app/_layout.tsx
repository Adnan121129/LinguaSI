import { focusManager, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DarkTheme, DefaultTheme, Stack, ThemeProvider as NavigationTheme } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import { CloudOff } from "lucide-react-native";
import { useEffect, useRef, useState } from "react";
import { AppState, View } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { ToastProvider } from "@/components/toast";
import { Button, Text } from "@/components/ui";
import { useMe } from "@/hooks/use-me";
import { ApiError, errorMessage } from "@/lib/api";
import { AuthProvider, useAuth } from "@/lib/auth";
import { API_URL } from "@/lib/config";
import { ThemeProvider, useTheme } from "@/lib/theme";

SplashScreen.preventAutoHideAsync();

// Refresh stale data when the learner comes back to the app ("return later and continue").
AppState.addEventListener("change", (state) => focusManager.setFocused(state === "active"));

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        // Client errors (validation, not found, forbidden) won't fix themselves; network blips might.
        retry: (count, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 2,
      },
    },
  });
}

export default function RootLayout() {
  const [queryClient] = useState(createQueryClient);
  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <AuthProvider>
            <ToastProvider>
              <RootNavigator />
            </ToastProvider>
          </AuthProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

function Unreachable({ message, onRetry, onSignOut }: { message: string; onRetry: () => void; onSignOut?: () => void }) {
  const { colors } = useTheme();
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: 32, gap: 14, backgroundColor: colors.background }}>
      <CloudOff size={36} color={colors.mutedForeground} />
      <Text variant="heading" style={{ textAlign: "center" }}>Can&apos;t reach LinguaSI</Text>
      <Text tone="muted" style={{ textAlign: "center" }}>{message}</Text>
      <Text variant="caption" tone="muted" style={{ textAlign: "center" }}>Server: {API_URL}</Text>
      <Button title="Try again" onPress={onRetry} />
      {onSignOut ? <Button title="Sign out" variant="ghost" onPress={onSignOut} /> : null}
    </View>
  );
}

/** Adopt the theme saved in the learner's profile the first time it loads on this device. */
function useProfileTheme() {
  const { data: me } = useMe();
  const { setPreference } = useTheme();
  const adoptedFor = useRef<number | null>(null);
  useEffect(() => {
    if (!me || adoptedFor.current === me.id) return;
    adoptedFor.current = me.id;
    if (me.profile.theme) setPreference(me.profile.theme);
  }, [me, setPreference]);
}

function RootNavigator() {
  const { status, retry, signOut } = useAuth();
  const { scheme, colors } = useTheme();
  const me = useMe();
  useProfileTheme();
  const ready = status !== "restoring" && !(status === "signedIn" && me.isLoading);

  useEffect(() => {
    if (ready) SplashScreen.hideAsync();
  }, [ready]);

  if (!ready) return null; // the native splash screen stays up meanwhile
  if (status === "unreachable") return <Unreachable message="Your progress is safe. Check your connection, then try again." onRetry={retry} />;
  if (status === "signedIn" && !me.data) return <Unreachable message={errorMessage(me.error)} onRetry={() => me.refetch()} onSignOut={signOut} />;

  const signedIn = status === "signedIn";
  const onboarded = !!me.data?.profile.onboarding_completed;
  const base = scheme === "dark" ? DarkTheme : DefaultTheme;
  const navigationTheme = {
    ...base,
    colors: { ...base.colors, primary: colors.primary, background: colors.background, card: colors.card, text: colors.foreground, border: colors.border, notification: colors.danger },
  };

  return (
    <NavigationTheme value={navigationTheme}>
      <StatusBar style={scheme === "dark" ? "light" : "dark"} />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.background } }}>
        <Stack.Protected guard={!signedIn}>
          <Stack.Screen name="(auth)" />
        </Stack.Protected>
        <Stack.Protected guard={signedIn && !onboarded}>
          <Stack.Screen name="onboarding" />
        </Stack.Protected>
        <Stack.Protected guard={signedIn && onboarded}>
          <Stack.Screen name="(app)" />
        </Stack.Protected>
      </Stack>
    </NavigationTheme>
  );
}
