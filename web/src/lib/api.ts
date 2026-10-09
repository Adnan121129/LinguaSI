// Browser-side API client. Every call goes through the Next.js BFF (/api/backend/*), which attaches the
// session from httpOnly cookies; the browser never handles tokens or provider keys.

import { leaveSession } from "@/lib/navigation";

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

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  json?: unknown;
  form?: FormData;
  signal?: AbortSignal;
};

const NETWORK_MESSAGE = "You appear to be offline or the server can't be reached. Please check your connection and try again.";

function redirectToLogin() {
  if (typeof window === "undefined") return;
  const here = `${window.location.pathname}${window.location.search}`;
  if (!window.location.pathname.startsWith("/login")) leaveSession(`/login?next=${encodeURIComponent(here)}`);
}

async function parseError(response: Response): Promise<ApiError> {
  const body = await response.json().catch(() => null);
  const error = body?.error;
  if (error?.message) return new ApiError(response.status, error.code ?? "error", error.message, error.details, error.request_id);
  const fallback =
    response.status >= 500
      ? "Something went wrong on our side. Your work is saved - please try again in a moment."
      : "That request couldn't be completed.";
  return new ApiError(response.status, "error", fallback);
}

export async function request<T>(url: string, options: RequestOptions = {}): Promise<T> {
  const init: RequestInit = { method: options.method ?? (options.json || options.form ? "POST" : "GET"), signal: options.signal, credentials: "same-origin" };
  if (options.form) {
    init.body = options.form;
  } else if (options.json !== undefined) {
    init.body = JSON.stringify(options.json);
    init.headers = { "content-type": "application/json" };
  }
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "network_error", NETWORK_MESSAGE);
  }
  if (!response.ok) {
    const error = await parseError(response);
    if (response.status === 401 && url.startsWith("/api/backend/")) redirectToLogin();
    throw error;
  }
  if (response.status === 204) return undefined as T;
  const type = response.headers.get("content-type") ?? "";
  if (type.includes("application/json")) return (await response.json()) as T;
  return (await response.blob()) as T;
}

/** Call the LinguaSI API, e.g. api<Dashboard>("/dashboard"). */
export function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return request<T>(`/api/backend${path}`, options);
}

/** Relative audio URLs from the API (e.g. /speaking/audio/12) are served through the BFF. */
export function mediaUrl(path: string | null | undefined): string | null {
  return path ? `/api/backend${path}` : null;
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
