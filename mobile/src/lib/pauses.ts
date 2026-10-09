export type PauseStats = { measured: true; count: number; long_count: number; total_silence_seconds: number };

const SILENCE_DB = -42; // input level (dBFS) below which a sample counts as silence
const PAUSE_SECONDS = 0.6;
const LONG_PAUSE_SECONDS = 2.0;

/**
 * Pause statistics from the microphone level, measured the same way as the web recorder: silences of
 * 0.6s+ after the learner starts speaking count as pauses (2s+ as long pauses); trailing silence is
 * ignored. Returns null when the platform gave no level readings, so nothing is invented.
 */
export function pauseStats(levels: number[], sampleSeconds = 0.1): PauseStats | null {
  if (levels.length < 5) return null;
  let heardSpeech = false;
  let run = 0;
  let count = 0;
  let long = 0;
  let total = 0;
  const close = () => {
    const seconds = run * sampleSeconds;
    if (seconds >= PAUSE_SECONDS) {
      count += 1;
      total += seconds;
      if (seconds >= LONG_PAUSE_SECONDS) long += 1;
    }
    run = 0;
  };
  for (const level of levels) {
    if (level > SILENCE_DB) {
      if (heardSpeech) close();
      heardSpeech = true;
      run = 0;
    } else if (heardSpeech) {
      run += 1;
    }
  }
  return heardSpeech ? { measured: true, count, long_count: long, total_silence_seconds: Math.round(total * 10) / 10 } : null;
}
