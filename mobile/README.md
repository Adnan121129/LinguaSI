# LinguaSI mobile

The LinguaSI app for iOS and Android, built with Expo (SDK 57), React Native and TypeScript. It uses
the same REST API as the web app, so progress, mistakes, vocabulary and missions are shared: start an
essay on the web, review words on the bus, and the dashboard on either device reflects both.

## What's in the app

| Area | Screens |
| --- | --- |
| Bottom tabs | **Home** (AI estimated band, streak, level, SI recommendation with "Why this?", daily mission, insight, weekly minutes chart, skills, focus areas, "What SI changed"), **Practice** hub, **Vocabulary** (today, my words, word bank, insights), **Tutor** (SI Tutor chats), **Me** (progress, achievements, mistakes, settings, theme, sign out) |
| Skills | Writing (tasks, generate an original task, tutor/exam mode, timer, word count, autosave, hints, evaluation with tappable error highlights), Speaking (Parts 1–3 mock test, examiner voice, Part 2 preparation timer, recording, evaluation with replay), Reading and Listening (generated sets, IELTS question types, evidence, transcripts) |
| Improve | My Mistakes (charts, heatmap, recurring patterns, revision, per-mistake practice), targeted practice, English Lab (daily phrase + quiz, grammar, sentence building, pronunciation check, role-play conversations) |
| Account | Registration, onboarding, 15-minute diagnostic, progress charts, achievements and weekly challenges, settings (goals, routine, recordings, password, account deletion) |

Charts follow the same rules as the web app: each one is titled by the question it answers, has a
table view, and values can be inspected by tapping.

## Requirements

- Node.js 22 and npm
- The LinguaSI API running (see the root README) — Mock AI Mode works without any AI provider keys
- For a phone: Expo Go, or a development build (below)

## Configure

```sh
cp .env.example .env   # optional
```

`EXPO_PUBLIC_API_URL` is the only setting. When it is not set, the app talks to port 8000 on the
machine running the Metro bundler, which works from iOS simulators, Android emulators and from a phone
on the same Wi-Fi network (start the API with `--host 0.0.0.0` in that case). The value is compiled
into the app and is public by design. **No AI provider keys or other secrets ever go into the app** —
the server holds them, and every AI request goes through the API.

## Run

```sh
npm install
npx expo start          # then press a (Android), i (iOS) or scan the QR code
npx expo start --go     # open in Expo Go instead of a development build
npx expo start --web    # browser preview for development only (the production web client is ../web)
```

All native modules the app uses (audio, speech, secure storage, SVG) are included in Expo Go, so Expo
Go works for trying the app. For day-to-day development and release testing use a development build:

```sh
npx expo run:android            # local build (Android Studio / SDK required)
npx expo run:ios                # local build (macOS + Xcode)
npx eas-cli@latest build --profile development --platform android   # cloud build via EAS
```

`eas.json` defines `development`, `preview` and `production` profiles. Set `EXPO_PUBLIC_API_URL` for
each as an EAS environment variable (`npx eas-cli@latest env:create`), not in the repository.

## How sign-in works

- Sign-in and registration return an access token (kept in memory) and a rotating refresh token, stored
  in the iOS Keychain / Android Keystore via `expo-secure-store`.
- An expired access token is refreshed once, transparently. Refreshes are single-flight because the
  server rotates refresh tokens and treats a reused one as theft.
- Signing out revokes the refresh token on the server. Changing the password signs out other devices.

## Speech

- **Speaking answers** are recorded with `expo-audio` (with pause detection from the microphone level).
  When the server has a speech-to-text provider (`STT_PROVIDER=openai`), the recording is transcribed
  there. Without one (Mock AI Mode), the recording is kept for replay and the learner types what they
  said — or dictates it with the keyboard's microphone key. Those answers are labelled as typed and
  pronunciation is not scored, so the app never presents a guess as a pronunciation assessment.
- **Listening audio and the examiner's voice** use server-generated audio when a TTS provider is
  configured, otherwise the phone's own voices (`expo-speech`), with a different voice per speaker.
- **Pronunciation practice** is a clarity check: the phone's speech recognition (keyboard dictation)
  writes what it heard, and the server compares it with the target sentence.

## Quality checks

```sh
npm run typecheck   # TypeScript
npm run lint        # ESLint (eslint-config-expo)
npm test            # Jest + React Native Testing Library
```

## Structure

```
src/
  app/                    Expo Router routes (file = screen)
    (auth)/               sign in, register
    onboarding.tsx        first-run profile
    (app)/                everything behind sign-in (protected)
      (tabs)/             Home, Practice, Vocabulary, Tutor, Me
      writing/ speaking/ reading/ listening/ vocabulary/ practice/ lab/ tutor/
      diagnostic.tsx mistakes.tsx progress.tsx achievements.tsx settings.tsx
  components/             UI kit, charts, practice runner, recorder, chat, evaluations
  hooks/                  data and device hooks
  lib/                    API client, auth, theme, storage, speech, types, utils
```

Screens mirror the web app's paths (`/writing`, `/practice/new?focus=…`), so the links in
recommendations, missions and Lab cards — which come from the API — open the right screen on both.
