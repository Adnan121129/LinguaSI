// LinguaSI API client for the mobile app. It talks to the same REST API as the web app, using
// bearer tokens: a short-lived access token kept in memory and a rotating refresh token kept in
// secure storage. No AI provider credentials ever reach the device.

import { API_URL } from "@/lib/config";
import { tokenStore } from "@/lib/storage";
import type { User } from "@/lib/types";

export class ApiError extends Error {
  status: number;
  code: string;
  details?: unknown;
  requestId?: string;

  constructor(status: number, code: string, message: string, details?: unknown, requestId?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

export type TokenResponse = { access_token: string; refresh_token: string; expires_in: number; user: User };

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  json?: unknown;
  form?: FormData;
  signal?: AbortSignal;
  /** Send the access token (default). Sign-in and registration set this to false. */
  auth?: boolean;
};

export const NETWORK_MESSAGE = "LinguaSI can't reach the server. Check your connection and try again.";
const SESSION_ENDED_MESSAGE = "Your session has ended. Please sign in again.";

let accessToken: string | null = null;
let refreshToken: string | null = null;
let refreshing: Promise<TokenResponse | null> | null = null;
let sessionEndedHandler: (() => void) | null = null;

/** Store a fresh token pair (after sign-in, registration or a refresh). */
export async function applyTokens(tokens: Pick<TokenResponse, "access_token" | "refresh_token">): Promise<void> {
  accessToken = tokens.access_token;
  refreshToken = tokens.refresh_token;
  await tokenStore.set(tokens.refresh_token);
}

export async function clearTokens(): Promise<string | null> {
  const previous = refreshToken;
  accessToken = null;
  refreshToken = null;
  await tokenStore.clear();
  return previous;
}

/** Called when the server rejects the session for good (refresh token expired, revoked or reused). */
export function onSessionEnded(handler: (() => void) | null) {
  sessionEndedHandler = handler;
}

/** Authorization header for media the player fetches itself (recordings, generated audio). */
export function authHeaders(): Record<string, string> {
  return accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
}

export function mediaUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  return /^https?:/.test(path) ? path : `${API_URL}${path}`;
}

/**
 * Exchange the stored refresh token for a new pair. Only one refresh runs at a time: the server
 * rotates refresh tokens and treats a reused one as theft, so parallel refreshes would sign the
 * learner out everywhere. Returns null when the session is over; throws when offline.
 */
export async function refreshSession(token?: string): Promise<TokenResponse | null> {
  if (token) refreshToken = token;
  if (!refreshToken) return null;
  refreshing ??= (async () => {
    try {
      let response: Response;
      try {
        response = await fetch(`${API_URL}/auth/refresh`, {
          method: "POST",
          headers: { "content-type": "application/json", accept: "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      } catch {
        throw new ApiError(0, "network_error", NETWORK_MESSAGE);
      }
      if (response.status === 401 || response.status === 403) {
        await clearTokens();
        return null;
      }
      if (!response.ok) throw await parseError(response);
      const body = (await response.json()) as TokenResponse;
      await applyTokens(body);
      return body;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

async function parseError(response: Response): Promise<ApiError> {
  const body = await response.json().catch(() => null);
  const error = body?.error;
  if (error?.message) return new ApiError(response.status, error.code ?? "error", error.message, error.details, error.request_id);
  const fallback = response.status >= 500 ? "Something went wrong on our side. Your work is saved - please try again in a moment." : "That request couldn't be completed.";
  return new ApiError(response.status, "error", fallback);
}

async function send(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { accept: "application/json" };
  if (options.auth !== false && accessToken) headers.Authorization = `Bearer ${accessToken}`;
  let body: BodyInit | undefined;
  if (options.form) {
    body = options.form;
  } else if (options.json !== undefined) {
    body = JSON.stringify(options.json);
    headers["content-type"] = "application/json";
  }
  const method = options.method ?? (options.json !== undefined || options.form ? "POST" : "GET");
  try {
    return await fetch(`${API_URL}${path}`, { method, headers, body, signal: options.signal });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new ApiError(0, "network_error", NETWORK_MESSAGE);
  }
}

/** Call the LinguaSI API, e.g. api<Dashboard>("/dashboard"). Refreshes an expired access token once. */
export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await send(path, options);
  if (response.status === 401 && options.auth !== false && refreshToken) {
    if (await refreshSession()) {
      response = await send(path, options);
    } else {
      sessionEndedHandler?.();
      throw new ApiError(401, "session_ended", SESSION_ENDED_MESSAGE);
    }
  }
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  const type = response.headers.get("content-type") ?? "";
  if (type.includes("application/json")) return (await response.json()) as T;
  return (await response.text()) as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return "Something went wrong. Please try again.";
}

export function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || error.code !== "validation_error") return {};
  const fields = (error.details as { fields?: { field: string; message: string }[] } | undefined)?.fields ?? [];
  return Object.fromEntries(fields.map((f) => [f.field, f.message]));
}
