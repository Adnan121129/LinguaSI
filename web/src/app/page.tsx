import { Brain, CalendarCheck, Headphones, Mic, PenLine, Repeat, ShieldCheck, Target } from "lucide-react";
import Link from "next/link";

import { OFFICIAL_DISCLAIMER } from "@/components/band";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { buttonClasses } from "@/components/ui/styles";

const FEATURES = [
  { icon: PenLine, title: "Writing tutor & examiner", text: "Hints while you write, then criterion-by-criterion AI estimated bands with every error highlighted." },
  { icon: Mic, title: "Speaking mock tests", text: "Parts 1–3 with follow-up questions, recordings, transcripts, fluency metrics and honest pronunciation notes." },
  { icon: Target, title: "My Mistakes tracker", text: "Every error is stored, grouped and turned into five-minute repair challenges until you master it." },
  { icon: Repeat, title: "Adaptive vocabulary", text: "Spaced repetition across ten exercise types, with words you use in writing and speaking counted as practice." },
  { icon: Headphones, title: "Reading & listening", text: "Original passages and recordings at your level, with evidence for every answer." },
  { icon: CalendarCheck, title: "Daily AI mission", text: "A short plan built from your own data, with a clear reason for every task." },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5 sm:px-6">
        <Logo />
        <div className="flex items-center gap-2">
          <ThemeToggle compact persist={false} />
          <Link href="/login" className={buttonClasses("ghost", "sm")}>
            Sign in
          </Link>
          <Link href="/register" className={buttonClasses("primary", "sm")}>
            Start free
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 pb-16 sm:px-6">
        <section className="grid items-center gap-10 py-12 lg:grid-cols-2 lg:py-20">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full bg-primary-soft px-3 py-1 text-xs font-medium text-primary">
              <Brain className="size-3.5" aria-hidden /> One intelligence layer across every skill
            </span>
            <h1 className="mt-4 text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
              Learn English with a coach that <span className="text-primary">remembers every mistake</span>.
            </h1>
            <p className="mt-4 max-w-xl text-lg text-muted-foreground">
              LinguaSI connects your writing, speaking, vocabulary, reading and listening. A mistake in one skill shapes the practice you get in all
              the others — so you improve faster, with less guesswork.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/register" className={buttonClasses("primary", "lg")}>
                Take the free diagnostic
              </Link>
              <Link href="/login" className={buttonClasses("outline", "lg")}>
                I already have an account
              </Link>
            </div>
            <p className="mt-6 flex items-start gap-2 text-xs text-muted-foreground">
              <ShieldCheck className="mt-0.5 size-4 shrink-0" aria-hidden /> {OFFICIAL_DISCLAIMER}
            </p>
          </div>
          <div className="rounded-3xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
            <p className="text-sm font-medium text-muted-foreground">Example: what SI does after one essay</p>
            <ol className="mt-4 space-y-3 text-sm">
              {[
                "Writing Examiner estimates each criterion and highlights 7 errors in your text.",
                "Error Analyst notices article mistakes appeared in 3 of your last 4 essays.",
                "Practice Generator builds a 5-minute Article Repair Challenge from your own sentences.",
                "Vocabulary Engine adds the collocations you misused to tomorrow's review.",
                "Learning Planner moves article practice into your next daily mission — and tells you why.",
              ].map((step, index) => (
                <li key={step} className="flex gap-3">
                  <span className="grid size-6 shrink-0 place-items-center rounded-full bg-primary-soft text-xs font-semibold text-primary">{index + 1}</span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section aria-labelledby="features" className="py-8">
          <h2 id="features" className="text-2xl font-semibold tracking-tight">
            Everything in one adaptive plan
          </h2>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <div key={title} className="rounded-2xl border border-border bg-card p-5">
                <Icon className="size-5 text-primary" aria-hidden />
                <h3 className="mt-3 font-semibold">{title}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{text}</p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="border-t border-border py-6 text-center text-xs text-muted-foreground">
        LinguaSI is an independent learning tool and is not affiliated with or endorsed by IELTS, the British Council, IDP or Cambridge.
      </footer>
    </div>
  );
}
