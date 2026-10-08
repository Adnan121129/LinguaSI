import Link from "next/link";

import { buttonClasses } from "@/components/ui/styles";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-4 text-center">
      <p className="text-sm font-medium text-primary">404</p>
      <h1 className="text-2xl font-semibold">We couldn&apos;t find that page</h1>
      <p className="max-w-md text-sm text-muted-foreground">The link may be out of date, or the item may belong to another account.</p>
      <Link href="/dashboard" className={buttonClasses("primary")}>
        Back to your dashboard
      </Link>
    </div>
  );
}
