// Server-only helpers for the Backend-for-Frontend layer.
// Tokens live in httpOnly cookies, so browser JavaScript never sees them.
import type { NextRequest, NextResponse } from "next/server";

export const BACKEND_URL = (process.env.BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const ACCESS_COOKIE = "lsi_access";
export const REFRESH_COOKIE = "lsi_refresh";

const secure = process.env.COOKIE_SECURE ? process.env.COOKIE_SECURE === "true" : process.env.NODE_ENV === "production";
const REFRESH_MAX_AGE = 60 * 60 * 24 * 30;

export type TokenPayload = { access_token: string; refresh_token: string; expires_in: number; user?: unknown };

export function setSessionCookies(response: NextResponse, tokens: TokenPayload): void {
  response.cookies.set(ACCESS_COOKIE, tokens.access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/",
    maxAge: Math.max(60, tokens.expires_in - 30),
  });
  response.cookies.set(REFRESH_COOKIE, tokens.refresh_token, {
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/",
    maxAge: REFRESH_MAX_AGE,
  });
}

export function clearSessionCookies(response: NextResponse): void {
  for (const name of [ACCESS_COOKIE, REFRESH_COOKIE]) {
    response.cookies.set(name, "", { httpOnly: true, sameSite: "lax", secure, path: "/", maxAge: 0 });
  }
}

/** Headers that identify the end user to the API (for rate limiting and logs). */
export function forwardedHeaders(request: NextRequest): Record<string, string> {
  const headers: Record<string, string> = {};
  const forwardedFor = request.headers.get("x-forwarded-for");
  if (forwardedFor) headers["x-forwarded-for"] = forwardedFor;
  // With the shared secret, the API accepts the learner address we report even though this server's
  // own address changes (as on Vercel). The right-most entry is the one our own proxy added.
  const secret = process.env.PROXY_SHARED_SECRET;
  const learnerAddress = forwardedFor?.split(",").at(-1)?.trim();
  if (secret && learnerAddress) {
    headers["x-linguasi-proxy-secret"] = secret;
    headers["x-linguasi-client-ip"] = learnerAddress;
  }
  const userAgent = request.headers.get("user-agent");
  if (userAgent) headers["user-agent"] = userAgent;
  const requestId = request.headers.get("x-request-id");
  if (requestId) headers["x-request-id"] = requestId;
  return headers;
}

// Requests that arrive together just after the access token expired all carry the same refresh token.
// They share one refresh, so every response hands the browser the same new tokens.
const SHARE_REFRESH_MS = 10_000;
const sharedRefreshes = new Map<string, Promise<TokenPayload | null>>();

export function refreshSession(refreshToken: string, request: NextRequest): Promise<TokenPayload | null> {
  const shared = sharedRefreshes.get(refreshToken);
  if (shared) return shared;
  const refresh = requestRefresh(refreshToken, request);
  sharedRefreshes.set(refreshToken, refresh);
  void refresh.then((tokens) => {
    if (tokens) setTimeout(() => sharedRefreshes.delete(refreshToken), SHARE_REFRESH_MS);
    else sharedRefreshes.delete(refreshToken);
  });
  return refresh;
}

async function requestRefresh(refreshToken: string, request: NextRequest): Promise<TokenPayload | null> {
  try {
    const response = await fetch(`${BACKEND_URL}/auth/refresh`, {
      method: "POST",
      headers: { "content-type": "application/json", ...forwardedHeaders(request) },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as TokenPayload;
  } catch {
    return null;
  }
}

export function unavailable(): Response {
  return Response.json(
    { error: { code: "service_unavailable", message: "LinguaSI can't reach its server right now. Please try again in a moment." } },
    { status: 503 },
  );
}
