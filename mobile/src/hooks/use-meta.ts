import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

export type Meta = { ai: { provider: string; mock_mode: boolean }; speech: { stt_provider: string; tts_provider: string }; disclaimer: string };

/** Public server configuration: which AI and speech providers are active (never any credentials). */
export function useMeta() {
  return useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/meta", { auth: false }), staleTime: 300_000 });
}
