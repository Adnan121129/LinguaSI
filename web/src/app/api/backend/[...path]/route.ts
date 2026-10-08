// Authenticated proxy from the browser to the LinguaSI API.
// The access token is attached from an httpOnly cookie and silently refreshed once when it expires.
import { NextResponse, type NextRequest } from "next/server";

import {
  ACCESS_COOKIE,
  BACKEND_URL,
  REFRESH_COOKIE,
  clearSessionCookies,
  forwardedHeaders,
  refreshSession,
  setSessionCookies,
  unavailable,
  type TokenPayload,
} from "@/lib/server/session";

const SAFE_SEGMENT = /^[A-Za-z0-9_.\-]+$/;
// content-length is not forwarded: fetch transparently decompresses gzip, so the upstream length would be wrong.
const PASS_RESPONSE_HEADERS = ["content-type", "content-disposition", "cache-control", "x-request-id"];

async function forward(request: NextRequest, path: string[], accessToken: string | undefined, body: ArrayBuffer | null): Promise<Response> {
  const url = `${BACKEND_URL}/${path.join("/")}${request.nextUrl.search}`;
  const headers: Record<string, string> = { ...forwardedHeaders(request), accept: request.headers.get("accept") ?? "application/json" };
  const contentType = request.headers.get("content-type");
  if (contentType) headers["content-type"] = contentType;
  if (accessToken) headers.authorization = `Bearer ${accessToken}`;
  return fetch(url, { method: request.method, headers, body, cache: "no-store", redirect: "manual" });
}

async function handle(request: NextRequest, context: RouteContext<"/api/backend/[...path]">): Promise<Response> {
  const { path } = await context.params;
  if (!path.length || path.some((segment) => !SAFE_SEGMENT.test(segment) || segment === "..")) {
    return NextResponse.json({ error: { code: "not_found", message: "Not found." } }, { status: 404 });
  }
  const body = request.method === "GET" || request.method === "HEAD" ? null : await request.arrayBuffer();
  let accessToken = request.cookies.get(ACCESS_COOKIE)?.value;
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
  let refreshed: TokenPayload | null = null;

  if (!accessToken && refreshToken) {
    refreshed = await refreshSession(refreshToken, request);
    accessToken = refreshed?.access_token;
  }

  let upstream: Response;
  try {
    upstream = await forward(request, path, accessToken, body);
    if (upstream.status === 401 && refreshToken && !refreshed) {
      refreshed = await refreshSession(refreshToken, request);
      if (refreshed) upstream = await forward(request, path, refreshed.access_token, body);
    }
  } catch {
    return unavailable();
  }

  const headers = new Headers();
  for (const name of PASS_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  const response = new NextResponse(upstream.body, { status: upstream.status, headers });
  if (refreshed) setSessionCookies(response, refreshed);
  else if (upstream.status === 401 && refreshToken) clearSessionCookies(response);
  return response;
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
