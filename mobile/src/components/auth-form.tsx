import { Link } from "expo-router";
import { useRef, useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Logo } from "@/components/logo";
import { Button, Card, Input, Notice, Text } from "@/components/ui";
import { errorMessage, fieldErrors } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { API_URL } from "@/lib/config";
import { useTheme } from "@/lib/theme";

/** Shared sign-in / registration form. Tokens go to secure storage; the root layout routes onwards. */
export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const { signIn, register } = useAuth();
  const { colors } = useTheme();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const emailRef = useRef<TextInput>(null);
  const passwordRef = useRef<TextInput>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    setFields({});
    try {
      if (mode === "login") await signIn(email.trim(), password);
      else await register({ name: name.trim(), email: email.trim(), password });
    } catch (err) {
      setFields(fieldErrors(err));
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: "center", padding: 20, gap: 24 }} keyboardShouldPersistTaps="handled">
          <View style={{ alignItems: "center", gap: 8 }}>
            <Logo size={40} />
            <Text tone="muted" style={{ textAlign: "center" }}>Learn English. Master IELTS. Let Intelligence Adapt to You.</Text>
          </View>
          <Card style={{ padding: 20, gap: 16 }}>
            <View style={{ gap: 4 }}>
              <Text variant="title">{mode === "login" ? "Welcome back" : "Create your account"}</Text>
              <Text tone="muted">{mode === "login" ? "Sign in to continue your learning plan." : "Free to start. Your plan adapts after a 15-minute diagnostic."}</Text>
            </View>
            {mode === "register" ? (
              <Input label="Name" value={name} onChangeText={setName} autoComplete="name" textContentType="name" returnKeyType="next" onSubmitEditing={() => emailRef.current?.focus()} error={fields.name} maxLength={100} />
            ) : null}
            <Input
              ref={emailRef}
              label="Email"
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              autoComplete="email"
              keyboardType="email-address"
              textContentType="emailAddress"
              returnKeyType="next"
              onSubmitEditing={() => passwordRef.current?.focus()}
              error={fields.email}
            />
            <Input
              ref={passwordRef}
              label="Password"
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              textContentType={mode === "login" ? "password" : "newPassword"}
              returnKeyType="go"
              onSubmitEditing={submit}
              hint={mode === "register" ? "At least 8 characters, with a letter and a number." : undefined}
              error={fields.password}
            />
            {error ? <Notice tone="danger">{error}</Notice> : null}
            <Button title={mode === "login" ? "Sign in" : "Create account"} size="lg" loading={busy} onPress={submit} />
          </Card>
          <View style={{ alignItems: "center", gap: 10 }}>
            {mode === "login" ? (
              <Link href="/register" replace style={{ color: colors.primary, fontWeight: "600" }}>
                New to LinguaSI? Create an account
              </Link>
            ) : (
              <Link href="/login" replace style={{ color: colors.primary, fontWeight: "600" }}>
                Already have an account? Sign in
              </Link>
            )}
            <Text variant="caption" tone="muted">Server: {API_URL}</Text>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
