import { RecordingPresets, requestRecordingPermissionsAsync, setAudioModeAsync, useAudioRecorder, useAudioRecorderState } from "expo-audio";
import { useCallback, useEffect, useRef, useState } from "react";
import { Platform } from "react-native";

import { pauseStats, type PauseStats } from "@/lib/pauses";

export type Recording = { uri: string | null; mimeType: string; durationSeconds: number; pauses: PauseStats | null };

const SAMPLE_MS = 100;

/** Microphone recording for spoken answers (expo-audio). The audio is uploaded for replay and server transcription. */
export function useAnswerRecorder() {
  const recorder = useAudioRecorder({ ...RecordingPresets.HIGH_QUALITY, isMeteringEnabled: true });
  const state = useAudioRecorderState(recorder, SAMPLE_MS);
  const [phase, setPhase] = useState<"idle" | "requesting" | "recording">("idle");
  const [error, setError] = useState<string | null>(null);
  const levels = useRef<number[]>([]);

  // Collect input levels while recording (iOS and Android report metering; the web preview may not).
  useEffect(() => {
    if (state.isRecording && typeof state.metering === "number") levels.current.push(state.metering);
  }, [state]);

  const start = useCallback(async () => {
    setError(null);
    setPhase("requesting");
    try {
      const permission = await requestRecordingPermissionsAsync();
      if (!permission.granted) {
        setError("Microphone access is off. Allow it in Settings to record, or type your answer instead.");
        setPhase("idle");
        return false;
      }
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await recorder.prepareToRecordAsync();
      levels.current = [];
      recorder.record();
      setPhase("recording");
      return true;
    } catch {
      setError("Recording couldn't start on this device. You can type your answer instead.");
      setPhase("idle");
      return false;
    }
  }, [recorder]);

  const stop = useCallback(async (): Promise<Recording | null> => {
    if (phase !== "recording") return null;
    const durationSeconds = Math.round((recorder.getStatus().durationMillis / 1000) * 10) / 10;
    try {
      await recorder.stop();
    } finally {
      setPhase("idle");
      setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true }).catch(() => undefined);
    }
    const uri = recorder.uri;
    const mimeType = Platform.OS === "web" ? "audio/webm" : "audio/mp4";
    return { uri, mimeType, durationSeconds, pauses: pauseStats(levels.current) };
  }, [phase, recorder]);

  return { phase, error, elapsed: Math.floor(state.durationMillis / 1000), level: state.metering ?? null, start, stop };
}

/** Attach a recording to a multipart form (native file URI, or a Blob in the web preview). */
export async function appendRecording(form: FormData, recording: Recording) {
  if (!recording.uri) return;
  if (Platform.OS === "web") {
    const blob = await (await fetch(recording.uri)).blob();
    form.append("audio", blob, "answer.webm");
    return;
  }
  // React Native's FormData accepts { uri, name, type } file descriptors.
  form.append("audio", { uri: recording.uri, name: "answer.m4a", type: recording.mimeType } as unknown as Blob);
}
