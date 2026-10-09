// A screen that changes the navigation guards (finishing onboarding) can't navigate into the newly
// unlocked area in the same tick. It leaves the destination here and the app layout opens it on mount.
let pending: string | null = null;

export function setPendingRoute(route: string | null) {
  pending = route;
}

export function takePendingRoute(): string | null {
  const route = pending;
  pending = null;
  return route;
}
