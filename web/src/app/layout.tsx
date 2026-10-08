import type { Metadata, Viewport } from "next";

import { Providers } from "@/components/providers";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "LinguaSI — Super Intelligent English & IELTS Learning", template: "%s · LinguaSI" },
  description:
    "Adaptive English and IELTS-style practice: writing and speaking feedback, a personal mistake tracker, spaced-repetition vocabulary and daily AI missions. AI estimated bands are practice indicators, not official IELTS results.",
  applicationName: "LinguaSI",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f7f8fc" },
    { media: "(prefers-color-scheme: dark)", color: "#0b1020" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" suppressHydrationWarning className="h-full antialiased">
      <body className="min-h-full">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
