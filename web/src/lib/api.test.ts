import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, errorMessage, fieldErrors, mediaUrl, request } from "@/lib/api";
import { leaveSession } from "@/lib/navigation";
import { jsonResponse, mockFetch } from "@/test/render";

vi.mock("@/lib/navigation", () => ({ leaveSession: vi.fn() }));

describe("api client", () => {
  beforeEach(() => {
    vi.mocked(leaveSession).mockClear();
    window.history.replaceState(null, "", "/dashboard");
  });

  it("calls the BFF with JSON and returns the parsed body", async () => {
    const fetch = mockFetch(() => jsonResponse({ name: "Ayesha" }));
    await expect(api("/me", { method: "PATCH", json: { name: "Ayesha" } })).resolves.toEqual({ name: "Ayesha" });
    expect(fetch).toHaveBeenCalledWith("/api/backend/me", expect.objectContaining({ method: "PATCH", body: '{"name":"Ayesha"}', credentials: "same-origin" }));
  });

  it("uses POST when sending a body and GET otherwise", async () => {
    const fetch = mockFetch(() => jsonResponse({}));
    await api("/writing/submissions", { json: { text: "Essay" } });
    await api("/dashboard");
    expect(fetch.mock.calls.map(([, init]) => init?.method)).toEqual(["POST", "GET"]);
  });

  it("returns undefined for empty responses", async () => {
    mockFetch(() => new Response(null, { status: 204 }));
    await expect(api("/vocabulary/3", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("turns the API error envelope into an ApiError with per-field messages", async () => {
    mockFetch(() =>
      jsonResponse(
        {
          error: {
            code: "validation_error",
            message: "Please check the highlighted fields.",
            request_id: "req-1",
            details: { fields: [{ field: "email", message: "Enter a valid email address." }] },
          },
        },
        422,
      ),
    );
    const error = await api("/auth/register", { json: {} }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 422, code: "validation_error", requestId: "req-1" });
    expect(errorMessage(error)).toBe("Please check the highlighted fields.");
    expect(fieldErrors(error)).toEqual({ email: "Enter a valid email address." });
  });

  it("keeps server failures friendly and never shows raw upstream output", async () => {
    mockFetch(() => new Response("Traceback (most recent call last): KeyError", { status: 502 }));
    const error = await api("/dashboard").catch((e: unknown) => e);
    expect(errorMessage(error)).toBe("Something went wrong on our side. Your work is saved - please try again in a moment.");
    expect(fieldErrors(error)).toEqual({});
  });

  it("explains network failures in plain language", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const error = await api("/dashboard").catch((e: unknown) => e);
    expect(error).toMatchObject({ status: 0, code: "network_error" });
    expect(errorMessage(error)).toMatch(/offline or the server can't be reached/);
  });

  it("lets cancelled requests surface as aborts rather than errors to show", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new DOMException("The operation was aborted.", "AbortError")));
    await expect(api("/dashboard")).rejects.toMatchObject({ name: "AbortError" });
  });

  it("sends the learner to sign in, and back to the same page afterwards, when the session has expired", async () => {
    window.history.replaceState(null, "", "/writing/12?tab=feedback");
    mockFetch(() => jsonResponse({ error: { code: "not_authenticated", message: "Please sign in again." } }, 401));
    await expect(api("/writing/submissions/12")).rejects.toMatchObject({ status: 401 });
    expect(leaveSession).toHaveBeenCalledWith("/login?next=%2Fwriting%2F12%3Ftab%3Dfeedback");
  });

  it("does not redirect for a wrong password or when already on the sign-in page", async () => {
    mockFetch(() => jsonResponse({ error: { code: "invalid_credentials", message: "Email or password is incorrect." } }, 401));
    await expect(request("/api/auth/login", { json: { email: "a@b.co", password: "nope" } })).rejects.toMatchObject({ status: 401 });
    window.history.replaceState(null, "", "/login");
    await expect(api("/me")).rejects.toMatchObject({ status: 401 });
    expect(leaveSession).not.toHaveBeenCalled();
  });

  it("never bounces signed-out visitors away from the landing or registration pages", async () => {
    mockFetch(() => jsonResponse({ error: { code: "not_authenticated", message: "Please sign in." } }, 401));
    for (const page of ["/", "/register"]) {
      window.history.replaceState(null, "", page);
      await expect(api("/me")).rejects.toMatchObject({ status: 401 });
    }
    expect(leaveSession).not.toHaveBeenCalled();
  });

  it("serves recordings and generated audio through the BFF", () => {
    expect(mediaUrl("/speaking/audio/4")).toBe("/api/backend/speaking/audio/4");
    expect(mediaUrl(null)).toBeNull();
  });

  it("falls back to a generic message for unknown errors", () => {
    expect(errorMessage(new Error("Microphone permission was denied."))).toBe("Microphone permission was denied.");
    expect(errorMessage("weird")).toBe("Something went wrong. Please try again.");
  });
});
