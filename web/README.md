# LinguaSI web app

The LinguaSI web client: Next.js 16 (App Router, Cache Components), React 19, TypeScript,
Tailwind CSS v4 and TanStack Query. It uses the same REST API as the mobile app, so a learner's
progress, mistakes, vocabulary and missions are shared across devices.

## What's in it

| Area | Routes |
| --- | --- |
| Getting started | `/` (landing), `/register`, `/login`, `/onboarding` (profile), `/onboarding/diagnostic` (15-minute diagnostic and estimated level) |
| Home | `/dashboard`: AI estimated band, streak, level and XP, weekly minutes, SI recommendation with "Why this?", daily mission, learning insight, skills, focus areas, "What SI changed" |
| Skills | `/writing` and `/writing/[id]` (tasks, original task generator, tutor/exam editor with timer and autosave, evaluation with highlighted errors), `/speaking` and `/speaking/[id]` (Parts 1–3 mock test with examiner voice and evaluation), `/reading`, `/listening` (generated sets with evidence) |
| Improve | `/mistakes` (charts, heatmap, recurring patterns, mini practice), `/practice/new` and `/practice/[id]` (targeted practice), `/vocabulary` (spaced repetition, word bank, insights), `/lab` (daily phrase, grammar, sentence building, pronunciation check, role-play conversation), `/tutor` (SI Tutor) |
| Track | `/progress` (charts with table views), `/achievements` (achievements, weekly challenges) |
| Account | `/settings` (profile, goals, routine, theme, recordings, password, account deletion), `/admin` (admins only) |

## Requirements

- Node.js 22 and npm
- The LinguaSI API running (see the root README). Mock AI Mode works without any AI keys.

## Configure

```sh
cp .env.example .env.local
```

| Variable | Purpose |
| --- | --- |
| `BACKEND_URL` | Where this server reaches the API (default `http://localhost:8000`). Server-side only. |
| `COOKIE_SECURE` | Session cookies are HTTPS-only in production builds; set `false` only for plain-HTTP testing. |
| `PROXY_SHARED_SECRET` | Optional. The same value as the API's, so per-IP limits count each learner separately when this server's address isn't fixed (e.g. on Vercel). See [docs/deployment.md](../docs/deployment.md#4-client-addresses-and-rate-limits). |

No AI keys or other secrets belong here: the browser never talks to an AI provider or to the API
directly.

## Run

```sh
npm install
npm run dev                  # http://localhost:3000
npm run build && npm start   # production build
docker build -t linguasi-web .   # standalone production image (from this directory)
```

## How it talks to the API

The browser only ever calls this server (same origin). Route handlers under `src/app/api` form a
small backend-for-frontend:

- `/api/auth/login`, `/api/auth/register`, `/api/auth/logout` exchange credentials with the API and
  keep the access and refresh tokens in `httpOnly`, `SameSite=Lax` cookies that page JavaScript can't
  read.
- `/api/backend/[...path]` forwards everything else, attaching the access token. When it has expired
  it refreshes once (the API rotates refresh tokens) and retries; if the refresh fails, the cookies
  are cleared and the learner is sent to sign in, returning to the same page afterwards.
- `src/proxy.ts` redirects signed-out visitors away from app pages before they render. It is only a
  convenience: every authorization decision is made by the API.
- Signing out, deleting the account and session expiry do a full page load, so no previous learner's
  data stays in memory.

## Design notes

- Light, dark and system themes (`next-themes`). The choice is saved to the learner's profile and
  follows them to other devices, including the mobile app.
- Charts (Recharts) are titled by the question they answer, each has a table view, legends appear
  only for two or more series, and colours come from a palette checked for colour-blind separation.
- Speech uses the browser: live transcripts with the Web Speech API where available, recordings with
  pause detection from the microphone level, and device voices for listening scripts. Answers that
  were typed are labelled as typed.

## Quality checks

```sh
npm run lint        # ESLint (Next.js config)
npm run typecheck   # generates route types, then tsc
npm test            # Vitest + Testing Library
npm run e2e         # Playwright acceptance journey (needs the API running; see playwright.config.ts)
```

## Structure

```
src/
  app/
    (auth)/             sign in, register
    (app)/              signed-in pages (dashboard, writing, speaking, ...)
    api/                backend-for-frontend route handlers
  components/           UI kit, charts, practice runner, recorder, evaluations
  hooks/                current learner, time on task
  lib/                  API client, types, formatting, speech helpers
    server/             session cookies and auth helpers (server only)
  proxy.ts              optimistic route protection
e2e/                    Playwright acceptance journey
```
