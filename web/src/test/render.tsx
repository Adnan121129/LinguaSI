import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { vi } from "vitest";

import { ToastProvider } from "@/components/providers/toast";

/** Renders inside the same providers the app uses (React Query without retries, toasts). */
export function renderWithProviders(ui: ReactElement, options?: RenderOptions) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );
  return { queryClient, ...render(ui, { wrapper, ...options }) };
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

/** Replaces global fetch with a mock that answers each call from `handler` and records the calls. */
export function mockFetch(handler: (url: string, init: RequestInit) => Response | Promise<Response>) {
  const fn = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => handler(String(input), init));
  vi.stubGlobal("fetch", fn);
  return fn;
}
