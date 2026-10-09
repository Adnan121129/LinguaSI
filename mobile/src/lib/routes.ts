import type { Href } from "expo-router";

// The API links recommendations, missions and Lab cards to screens using the web app's paths.
// Mobile screens mirror those paths, so only a few need translating.
const ALIASES: Record<string, string> = {
  "/dashboard": "/",
  "/onboarding": "/",
  "/onboarding/diagnostic": "/diagnostic",
  "/settings": "/settings",
};

export function appHref(route: string | null | undefined): Href {
  if (!route) return "/";
  const [path, query] = route.split("?");
  const target = ALIASES[path] ?? path;
  return (query ? `${target}?${query}` : target) as Href;
}
