import type { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { forwardedHeaders } from "./session";

const request = (headers: Record<string, string>) => ({ headers: new Headers(headers) }) as unknown as NextRequest;
const SECRET = "a-long-random-shared-secret-0123456789";

describe("forwardedHeaders", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("vouches for the address added by the proxy in front of the web server", () => {
    vi.stubEnv("PROXY_SHARED_SECRET", SECRET);
    // A client can prepend anything to X-Forwarded-For; the right-most entry comes from our own proxy.
    expect(forwardedHeaders(request({ "x-forwarded-for": "198.51.100.1, 203.0.113.7", "user-agent": "Browser" }))).toEqual({
      "x-forwarded-for": "198.51.100.1, 203.0.113.7",
      "x-linguasi-proxy-secret": SECRET,
      "x-linguasi-client-ip": "203.0.113.7",
      "user-agent": "Browser",
    });
  });

  it("sends no secret when none is configured", () => {
    vi.stubEnv("PROXY_SHARED_SECRET", "");
    expect(forwardedHeaders(request({ "x-forwarded-for": "203.0.113.7" }))).toEqual({ "x-forwarded-for": "203.0.113.7" });
  });
});
