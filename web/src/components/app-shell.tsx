"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  Bot,
  FlaskConical,
  Headphones,
  LayoutDashboard,
  Library,
  LineChart,
  LogOut,
  Menu,
  Mic,
  PenLine,
  Settings,
  Shield,
  Target,
  Trophy,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useLayoutEffect, useState, type ReactNode } from "react";

import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { Badge, PageSkeleton } from "@/components/ui";
import { useMe } from "@/hooks/use-me";
import { api, request } from "@/lib/api";
import { cn } from "@/lib/utils";

type NavItem = { href: string; label: string; icon: typeof LayoutDashboard };
const NAV: { group: string; items: NavItem[] }[] = [
  { group: "", items: [{ href: "/dashboard", label: "Dashboard", icon: LayoutDashboard }] },
  {
    group: "Practise",
    items: [
      { href: "/writing", label: "Writing", icon: PenLine },
      { href: "/speaking", label: "Speaking", icon: Mic },
      { href: "/reading", label: "Reading", icon: BookOpen },
      { href: "/listening", label: "Listening", icon: Headphones },
      { href: "/vocabulary", label: "Vocabulary", icon: Library },
      { href: "/lab", label: "English Lab", icon: FlaskConical },
    ],
  },
  {
    group: "Improve",
    items: [
      { href: "/mistakes", label: "My Mistakes", icon: Target },
      { href: "/tutor", label: "SI Tutor", icon: Bot },
    ],
  },
  {
    group: "Track",
    items: [
      { href: "/progress", label: "Progress", icon: LineChart },
      { href: "/achievements", label: "Achievements", icon: Trophy },
    ],
  },
];

function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`) || (href === "/mistakes" && pathname.startsWith("/practice"));
}

function NavLinks({ pathname, isAdmin, onNavigate }: { pathname: string; isAdmin: boolean; onNavigate?: () => void }) {
  const groups = isAdmin ? [...NAV, { group: "Admin", items: [{ href: "/admin", label: "Admin panel", icon: Shield }] }] : NAV;
  return (
    <nav aria-label="Main" className="space-y-5">
      {groups.map(({ group, items }) => (
        <div key={group || "home"}>
          {group && <p className="px-3 pb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{group}</p>}
          <ul className="space-y-0.5">
            {items.map(({ href, label, icon: Icon }) => {
              const active = isActive(pathname, href);
              return (
                <li key={href}>
                  <Link
                    href={href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition",
                      active ? "bg-primary-soft text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground",
                    )}
                  >
                    <Icon className="size-4" aria-hidden />
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: me, isLoading } = useMe();
  const { data: meta } = useQuery({ queryKey: ["meta"], queryFn: () => api<{ ai: { mock_mode: boolean; provider: string } }>("/meta"), staleTime: 300_000 });
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Close the mobile drawer when this page is hidden by a navigation.
  useLayoutEffect(() => () => setDrawerOpen(false), []);

  const needsOnboarding = !!me && !me.profile.onboarding_completed && !pathname.startsWith("/onboarding");
  useEffect(() => {
    if (needsOnboarding) router.replace("/onboarding");
  }, [needsOnboarding, router]);

  async function signOut() {
    await request("/api/auth/logout", { method: "POST" }).catch(() => undefined);
    queryClient.clear();
    window.location.assign("/login");
  }

  const sidebar = (
    <div className="flex h-full flex-col gap-6 p-4">
      <div className="flex items-center justify-between px-2 pt-1">
        <Logo href="/dashboard" />
      </div>
      <div className="flex-1 overflow-y-auto">
        <NavLinks pathname={pathname} isAdmin={me?.role === "admin"} onNavigate={() => setDrawerOpen(false)} />
      </div>
      <div className="space-y-3 border-t border-border pt-4">
        <Link
          href="/settings"
          onClick={() => setDrawerOpen(false)}
          className={cn("flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium", isActive(pathname, "/settings") ? "bg-primary-soft text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground")}
        >
          <Settings className="size-4" aria-hidden /> Settings
        </Link>
        <button onClick={signOut} className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground">
          <LogOut className="size-4" aria-hidden /> Sign out
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen lg:pl-64">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-border bg-card lg:block">{sidebar}</aside>

      {drawerOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <button className="absolute inset-0 bg-black/40" aria-label="Close menu" onClick={() => setDrawerOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-72 max-w-[85vw] border-r border-border bg-card shadow-xl">
            <button className="absolute right-3 top-4 rounded-lg p-1.5 text-muted-foreground hover:bg-muted" onClick={() => setDrawerOpen(false)} aria-label="Close menu">
              <X className="size-5" />
            </button>
            {sidebar}
          </div>
        </div>
      )}

      <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-3 border-b border-border bg-background/85 px-4 backdrop-blur sm:px-6">
        <div className="flex items-center gap-2">
          <button className="rounded-lg p-1.5 hover:bg-muted lg:hidden" onClick={() => setDrawerOpen(true)} aria-label="Open menu">
            <Menu className="size-5" />
          </button>
          <div className="lg:hidden">
            <Logo href="/dashboard" />
          </div>
        </div>
        <div className="flex items-center gap-2">
          {meta?.ai.mock_mode && (
            <Badge tone="warning" className="hidden sm:inline-flex" >
              Mock AI Mode
            </Badge>
          )}
          <ThemeToggle compact />
          {me && (
            <Link href="/settings" className="grid size-8 place-items-center rounded-full bg-primary-soft text-sm font-semibold text-primary" aria-label="Account settings" title={me.name}>
              {me.name.slice(0, 1).toUpperCase()}
            </Link>
          )}
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:py-8">
        {(isLoading || needsOnboarding) && <PageSkeleton />}
        {/* The page stays mounted (just hidden) while the session loads, so navigation can be prerendered instantly. */}
        <div className={cn(isLoading || needsOnboarding ? "hidden" : undefined)}>{children}</div>
      </main>
    </div>
  );
}
