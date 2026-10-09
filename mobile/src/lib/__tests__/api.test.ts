import { ApiError, api, applyTokens, clearTokens, errorMessage, fieldErrors, onSessionEnded } from "@/lib/api";

jest.mock("@/lib/storage", () => ({ tokenStore: { get: jest.fn(), set: jest.fn(), clear: jest.fn() } }));
jest.mock("@/lib/config", () => ({ API_URL: "https://api.test" }));

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const user = { id: 1, email: "a@b.co", name: "A", role: "learner", is_demo: false, created_at: "", profile: {} };

describe("api client", () => {
  let fetchMock: jest.Mock;

  beforeEach(async () => {
    fetchMock = jest.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    await clearTokens();
    onSessionEnded(null);
  });

  it("sends the access token and parses JSON", async () => {
    await applyTokens({ access_token: "access-1", refresh_token: "refresh-1" });
    fetchMock.mockResolvedValueOnce(json({ ok: true }));
    await expect(api("/dashboard")).resolves.toEqual({ ok: true });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("https://api.test/dashboard");
    expect(init.headers.Authorization).toBe("Bearer access-1");
  });

  it("never sends credentials to sign-in endpoints", async () => {
    await applyTokens({ access_token: "access-1", refresh_token: "refresh-1" });
    fetchMock.mockResolvedValueOnce(json({ access_token: "x" }));
    await api("/auth/login", { json: { email: "a@b.co", password: "p" }, auth: false });
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBeUndefined();
  });

  it("refreshes an expired access token once, even for parallel requests, then retries them", async () => {
    await applyTokens({ access_token: "old", refresh_token: "refresh-1" });
    fetchMock.mockImplementation(async (url: string, init: { headers: Record<string, string> }) => {
      if (url.endsWith("/auth/refresh")) return json({ access_token: "new", refresh_token: "refresh-2", expires_in: 900, user });
      return init.headers.Authorization === "Bearer new" ? json({ ok: url }) : json({ error: { code: "token_expired", message: "Expired" } }, 401);
    });
    const [a, b] = await Promise.all([api("/dashboard"), api("/me")]);
    expect(a).toEqual({ ok: "https://api.test/dashboard" });
    expect(b).toEqual({ ok: "https://api.test/me" });
    // The server rotates refresh tokens and treats reuse as theft, so only one refresh may happen.
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/auth/refresh"))).toHaveLength(1);
  });

  it("ends the session when the refresh token is no longer valid", async () => {
    const ended = jest.fn();
    onSessionEnded(ended);
    await applyTokens({ access_token: "old", refresh_token: "refresh-1" });
    fetchMock.mockImplementation(async (url: string) =>
      url.endsWith("/auth/refresh") ? json({ error: { code: "session_revoked", message: "Ended" } }, 401) : json({ error: { code: "token_expired", message: "Expired" } }, 401),
    );
    await expect(api("/dashboard")).rejects.toMatchObject({ status: 401, code: "session_ended" });
    expect(ended).toHaveBeenCalledTimes(1);
  });

  it("explains network failures and keeps validation messages per field", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Network request failed"));
    const offline = await api("/dashboard").catch((e: unknown) => e);
    expect(offline).toBeInstanceOf(ApiError);
    expect(errorMessage(offline)).toMatch(/can't reach the server/);

    fetchMock.mockResolvedValueOnce(json({ error: { code: "validation_error", message: "Check the fields", details: { fields: [{ field: "email", message: "Enter a valid email" }] } } }, 422));
    const invalid = await api("/auth/register", { json: {}, auth: false }).catch((e: unknown) => e);
    expect(fieldErrors(invalid)).toEqual({ email: "Enter a valid email" });
  });
});
