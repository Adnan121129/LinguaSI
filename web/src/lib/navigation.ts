/**
 * Full document navigation for session boundaries (sign-out, account deletion, expired session).
 * A client-side router push would keep the previous learner's cached queries and the route trees
 * that Next.js preserves for back/forward navigation in memory; a fresh document load drops all of it.
 */
export function leaveSession(path: string) {
  if (typeof window === "undefined") return;
  window.location.assign(path);
}
