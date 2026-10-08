import Link from "next/link";

export function Logo({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="flex items-center gap-2 font-semibold tracking-tight" aria-label="LinguaSI home">
      <span className="grid size-8 place-items-center rounded-xl bg-gradient-to-br from-indigo-500 to-sky-500 text-sm font-bold text-white shadow-sm">Li</span>
      <span>
        Lingua<span className="text-primary">SI</span>
      </span>
    </Link>
  );
}
