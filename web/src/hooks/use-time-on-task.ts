"use client";

import { useCallback, useEffect, useRef } from "react";

/**
 * Time on task for submissions: returns a function giving whole seconds since the activity was
 * first shown. The start is recorded once, after mount, so render stays pure and returning to a
 * page kept alive by the router does not restart the clock.
 */
export function useTimeOnTask() {
  const startedAt = useRef<number | null>(null);
  useEffect(() => {
    if (startedAt.current === null) startedAt.current = Date.now();
  }, []);
  return useCallback(() => (startedAt.current === null ? 0 : Math.round((Date.now() - startedAt.current) / 1000)), []);
}
