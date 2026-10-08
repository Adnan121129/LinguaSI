// Optimistic route protection: the real authorization check always happens in the API.
import { NextResponse, type NextRequest } from "next/server";

const PUBLIC_ONLY = ["/login", "/register"];
const PROTECTED_PREFIXES = [
  "/dashboard",
  "/onboarding",
  "/writing",
  "/speaking",
  "/vocabulary",
  "/mistakes",
  "/practice",
  "/reading",
  "/listening",
  "/lab",
  "/tutor",
  "/progress",
  "/achievements",
  "/settings",
  "/admin",
];

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const signedIn = request.cookies.has("lsi_refresh");
  if (!signedIn && PROTECTED_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(login);
  }
  if (signedIn && (PUBLIC_ONLY.includes(pathname) || pathname === "/")) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|webp|ico|txt)$).*)"],
};
