import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, applyTokens, clearTokens, onSessionEnded, refreshSession, type TokenResponse } from "@/lib/api";
import { tokenStore } from "@/lib/storage";

/** restoring: reading the saved session at launch; unreachable: a saved session exists but the API can't be reached. */
export type AuthStatus = "restoring" | "signedOut" | "signedIn" | "unreachable";

type AuthContextValue = {
  status: AuthStatus;
  signIn: (email: string, password: string) => Promise<void>;
  register: (details: { name: string; email: string; password: string }) => Promise<void>;
  signOut: () => Promise<void>;
  retry: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

/** Resume the saved session at launch: refresh it, or report that the learner must sign in (or that the API is unreachable). */
async function readStoredSession(): Promise<{ session?: TokenResponse; status: AuthStatus }> {
  const stored = await tokenStore.get();
  if (!stored) return { status: "signedOut" };
  try {
    const session = await refreshSession(stored);
    return session ? { session, status: "signedIn" } : { status: "signedOut" };
  } catch {
    return { status: "unreachable" };
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>("restoring");

  const endSession = useCallback(() => {
    queryClient.clear();
    setStatus("signedOut");
  }, [queryClient]);

  const startSession = useCallback(
    (session: TokenResponse) => {
      queryClient.setQueryData(["me"], session.user);
      setStatus("signedIn");
    },
    [queryClient],
  );

  const restore = useCallback(() => {
    readStoredSession().then((result) => {
      if (result.session) startSession(result.session);
      else setStatus(result.status);
    });
  }, [startSession]);

  useEffect(() => {
    onSessionEnded(endSession);
    restore();
    return () => onSessionEnded(null);
  }, [endSession, restore]);

  const signIn = useCallback(
    async (email: string, password: string) => {
      const session = await api<TokenResponse>("/auth/login", { json: { email, password }, auth: false });
      await applyTokens(session);
      startSession(session);
    },
    [startSession],
  );

  const register = useCallback(
    async (details: { name: string; email: string; password: string }) => {
      const session = await api<TokenResponse>("/auth/register", { json: details, auth: false });
      await applyTokens(session);
      startSession(session);
    },
    [startSession],
  );

  const signOut = useCallback(async () => {
    const token = await clearTokens();
    if (token) api("/auth/logout", { json: { refresh_token: token }, auth: false }).catch(() => undefined);
    endSession();
  }, [endSession]);

  const retry = useCallback(() => {
    setStatus("restoring");
    restore();
  }, [restore]);

  const value = useMemo(() => ({ status, signIn, register, signOut, retry }), [status, signIn, register, signOut, retry]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
