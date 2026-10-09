import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // A self-contained server bundle for Docker / any Node host (Vercel ignores this and uses its own output).
  output: "standalone",
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
