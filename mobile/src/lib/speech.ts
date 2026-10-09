import * as Speech from "expo-speech";

// Device text-to-speech (expo-speech). Used when the server has no TTS provider configured, which
// is the default in Mock AI Mode: listening scripts and examiner questions are read by the phone.

export type SpeakerVoice = { id: string; gender?: string; accent?: string };

const ACCENT_LANGS: Record<string, string[]> = {
  british: ["en-GB"],
  american: ["en-US"],
  australian: ["en-AU", "en-GB"],
  canadian: ["en-CA", "en-US"],
  indian: ["en-IN", "en-GB"],
};
const FEMALE_HINTS = /(female|woman|samantha|victoria|karen|moira|tessa|serena|kate|susan|zira|hazel|libby|sonia|natasha|aria|jenny)/i;
const MALE_HINTS = /(male|man|daniel|alex|fred|oliver|arthur|george|david|mark|ryan|guy)/i;

export async function loadVoices(): Promise<Speech.Voice[]> {
  try {
    return await Speech.getAvailableVoicesAsync();
  } catch {
    return [];
  }
}

const lang = (v: Speech.Voice) => v.language.replace("_", "-");

/** A distinct English voice per speaker, matching accent and (when the device exposes it) gender. */
export function assignVoices(voices: Speech.Voice[], speakers: SpeakerVoice[]): Record<string, Speech.Voice | undefined> {
  const english = voices.filter((v) => lang(v).toLowerCase().startsWith("en"));
  const used = new Set<string>();
  const result: Record<string, Speech.Voice | undefined> = {};
  for (const speaker of speakers) {
    const langs = ACCENT_LANGS[(speaker.accent ?? "british").toLowerCase()] ?? ["en-GB"];
    const genderRe = speaker.gender === "female" ? FEMALE_HINTS : speaker.gender === "male" ? MALE_HINTS : null;
    const candidates = [
      ...english.filter((v) => langs.includes(lang(v)) && (!genderRe || genderRe.test(v.name))),
      ...english.filter((v) => langs.includes(lang(v))),
      ...english.filter((v) => !genderRe || genderRe.test(v.name)),
      ...english,
    ];
    const pick = candidates.find((v) => !used.has(v.identifier)) ?? candidates[0];
    if (pick) used.add(pick.identifier);
    result[speaker.id] = pick;
  }
  return result;
}

/** Speak and resolve when finished, stopped or failed (never rejects). */
export function speak(text: string, options: { voice?: Speech.Voice; rate?: number } = {}): Promise<void> {
  return new Promise((resolve) => {
    if (!text.trim()) return resolve();
    Speech.speak(text, {
      voice: options.voice?.identifier,
      language: options.voice?.language ?? "en-GB",
      rate: options.rate ?? 1,
      onDone: () => resolve(),
      onStopped: () => resolve(),
      onError: () => resolve(),
    });
  });
}

export function stopSpeaking() {
  Speech.stop().catch(() => undefined);
}
