import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

const REFRESH_TOKEN_KEY = "linguasi.refresh-token";

/**
 * Where the long-lived refresh token is kept. On iOS and Android it lives in the Keychain /
 * Keystore via expo-secure-store. The web build of this app is only a development preview (the
 * production web client is the Next.js app with httpOnly cookies), so there it is kept in
 * sessionStorage and disappears when the tab closes. Access tokens are only ever held in memory.
 */
export const tokenStore = {
  async get(): Promise<string | null> {
    if (Platform.OS === "web") return globalThis.sessionStorage?.getItem(REFRESH_TOKEN_KEY) ?? null;
    return SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
  },
  async set(token: string): Promise<void> {
    if (Platform.OS === "web") return globalThis.sessionStorage?.setItem(REFRESH_TOKEN_KEY, token);
    await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, token, { keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK });
  },
  async clear(): Promise<void> {
    if (Platform.OS === "web") return globalThis.sessionStorage?.removeItem(REFRESH_TOKEN_KEY);
    await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
  },
};

/** Non-sensitive preferences and drafts (theme choice, unsent essay text). */
export const prefs = {
  async get(key: string): Promise<string | null> {
    try {
      return await AsyncStorage.getItem(`linguasi.${key}`);
    } catch {
      return null;
    }
  },
  async set(key: string, value: string): Promise<void> {
    try {
      await AsyncStorage.setItem(`linguasi.${key}`, value);
    } catch {
      // Preferences are a convenience; failing to store one must never break the app.
    }
  },
  async remove(key: string): Promise<void> {
    try {
      await AsyncStorage.removeItem(`linguasi.${key}`);
    } catch {
      // See above.
    }
  },
};
