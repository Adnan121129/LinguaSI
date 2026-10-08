import type { NextRequest } from "next/server";

import { exchangeCredentials } from "@/lib/server/auth-route";

export async function POST(request: NextRequest) {
  return exchangeCredentials(request, "/auth/login");
}
