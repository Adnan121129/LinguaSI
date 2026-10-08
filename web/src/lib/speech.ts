// Browser speech helpers. Text-to-speech uses the device's voices (speechSynthesis); speech recognition uses the
// Web Speech API where the browser supports it. Both degrade gracefully: the UI always offers a text fallback.

export type SpeakerVoice = { id: string; gender?: string; accent?: string };

const ACCENT_LANGS: Record<string, string[]> = {
  british: ["en-GB"],
  american: ["en-US"],
  australian: ["en-AU", "en-GB"],
  canadian: ["en-CA", "en-US"],
  indian: ["en-IN", "en-GB"],
};

export function ttsSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
}

export function loadVoices(): Promise<SpeechSynthesisVoice[]> {
  if (!ttsSupported()) return Promise.resolve([]);
  const existing = window.speechSynthesis.getVoices();
  if (existing.length) return Promise.resolve(existing);
  return new Promise((resolve) => {
    const done = () => resolve(window.speechSynthesis.getVoices());
    window.speechSynthesis.addEventListener("voiceschanged", done, { once: true });
    window.setTimeout(done, 1200);
  });
}

const FEMALE_HINTS = /(female|woman|samantha|victoria|karen|moira|tessa|serena|kate|susan|zira|hazel|libby|sonia|natasha|aria|jenny|google uk english female)/i;
const MALE_HINTS = /(male|man|daniel|alex|fred|oliver|arthur|george|david|mark|ryan|guy|google uk english male)/i;

/** Choose a distinct English voice per speaker, matching accent and (when the device exposes it) gender. */
export function assignVoices(voices: SpeechSynthesisVoice[], speakers: SpeakerVoice[]): Record<string, SpeechSynthesisVoice | undefined> {
  const english = voices.filter((v) => v.lang.toLowerCase().startsWith("en"));
  const used = new Set<string>();
  const result: Record<string, SpeechSynthesisVoice | undefined> = {};
  for (const speaker of speakers) {
    const langs = ACCENT_LANGS[(speaker.accent ?? "british").toLowerCase()] ?? ["en-GB"];
    const genderRe = speaker.gender === "female" ? FEMALE_HINTS : speaker.gender === "male" ? MALE_HINTS : null;
    const candidates = [
      ...english.filter((v) => langs.some((l) => v.lang === l || v.lang.replace("_", "-") === l) && (!genderRe || genderRe.test(v.name))),
      ...english.filter((v) => langs.some((l) => v.lang.replace("_", "-") === l)),
      ...english.filter((v) => !genderRe || genderRe.test(v.name)),
      ...english,
    ];
    const pick = candidates.find((v) => !used.has(v.name)) ?? candidates[0];
    if (pick) used.add(pick.name);
    result[speaker.id] = pick;
  }
  return result;
}

export type SpeakOptions = { voice?: SpeechSynthesisVoice; rate?: number; pitch?: number };

export function speak(text: string, options: SpeakOptions = {}): Promise<void> {
  return new Promise((resolve) => {
    if (!ttsSupported() || !text.trim()) return resolve();
    const utterance = new SpeechSynthesisUtterance(text);
    if (options.voice) {
      utterance.voice = options.voice;
      utterance.lang = options.voice.lang;
    } else {
      utterance.lang = "en-GB";
    }
    utterance.rate = options.rate ?? 1;
    utterance.pitch = options.pitch ?? 1;
    utterance.onend = () => resolve();
    utterance.onerror = () => resolve();
    window.speechSynthesis.speak(utterance);
  });
}

export function stopSpeaking(): void {
  if (ttsSupported()) window.speechSynthesis.cancel();
}

// --- Speech recognition -------------------------------------------------------------------------

type RecognitionResultEvent = {
  resultIndex: number;
  results: ArrayLike<{ isFinal: boolean; 0: { transcript: string; confidence: number } }>;
};

export type Recognizer = {
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: RecognitionResultEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  continuous: boolean;
  interimResults: boolean;
  lang: string;
};

type RecognizerConstructor = new () => Recognizer;

export function recognitionConstructor(): RecognizerConstructor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: RecognizerConstructor; webkitSpeechRecognition?: RecognizerConstructor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function recognitionSupported(): boolean {
  return recognitionConstructor() !== null;
}
