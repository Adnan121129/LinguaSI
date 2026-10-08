import { NextResponse, type NextRequest } from "next/server";

import { BACKEND_URL, REFRESH_COOKIE, clearSessionCookies, forwardedHeaders } from "@/lib/server/session";

export async function POST(request: NextRequest) {
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
  if (refreshToken) {
    await fetch(`${BACKEND_URL}/auth/logout`, {
      method: "POST",
      headers: { "content-type": "application/json", ...forwardedHeaders(request) },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    }).catch(() => undefined); // signing out locally must work even if the API is down
  }
  const response = NextResponse.json({ message: "Signed out." });
  clearSessionCookies(response);
  return response;
}
