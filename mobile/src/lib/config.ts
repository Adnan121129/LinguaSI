import Constants from "expo-constants";
import { Platform } from "react-native";

/**
 * Base URL of the LinguaSI API.
 *
 * Set EXPO_PUBLIC_API_URL for real devices and release builds. It is a public address, not a
 * secret: AI provider keys exist only on the server and are never shipped in the app.
 * In development the API is assumed to run on port 8000 of the machine serving the Metro bundle,
 * which also works from a phone on the same Wi-Fi network.
 */
function resolveApiUrl(): string {
  const configured = process.env.EXPO_PUBLIC_API_URL?.trim();
  if (configured) return configured.replace(/\/+$/, "");
  const devHost = Constants.expoConfig?.hostUri?.split(":")[0];
  if (devHost) return `http://${devHost}:8000`;
  return Platform.OS === "android" ? "http://10.0.2.2:8000" : "http://localhost:8000";
}

export const API_URL = resolveApiUrl();
