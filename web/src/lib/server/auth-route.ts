import { NextResponse, type NextRequest } from "next/server";

import { BACKEND_URL, forwardedHeaders, setSessionCookies, unavailable, type TokenPayload } from "./session";

/** Shared implementation for /api/auth/login and /api/auth/register. */
export async function exchangeCredentials(request: NextRequest, backendPath: "/auth/login" | "/auth/register"): Promise<Response> {
  let body: string;
  try {
    body = JSON.stringify(await request.json());
  } catch {
    return NextResponse.json({ error: { code: "bad_request", message: "Invalid request." } }, { status: 400 });
  }
  let response: Response;
  try {
    response = await fetch(`${BACKEND_URL}${backendPath}`, {
      method: "POST",
      headers: { "content-type": "application/json", ...forwardedHeaders(request) },
      body,
      cache: "no-store",
    });
  } catch {
    return unavailable();
  }
  const data = await response.json().catch(() => null);
  if (!response.ok || !data) {
    return NextResponse.json(data ?? { error: { code: "error", message: "Sign-in failed." } }, { status: response.status || 500 });
  }
  const result = NextResponse.json({ user: (data as TokenPayload).user }, { status: response.status });
  setSessionCookies(result, data as TokenPayload);
  return result;
}
