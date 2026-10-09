import { Keyboard, Mic, Send, Square } from "lucide-react-native";
import { useEffect, useRef, useState } from "react";
import { View } from "react-native";

import { Button, Input, Notice, Row, Text } from "@/components/ui";
import { useAnswerRecorder, type Recording } from "@/hooks/use-answer-recorder";
import { ApiError } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import { formatDuration } from "@/lib/utils";

export type SpokenAnswer = { recording: Recording | null; transcript: string | null; source: "typed" | null };

/** Input level as a 0-1 bar (dBFS -60..0). */
function LevelMeter({ level, active }: { level: number | null; active: boolean }) {
  const { colors } = useTheme();
  const value = active && level !== null ? Math.max(0.04, Math.min(1, (level + 60) / 60)) : 0.04;
  return (
    <View accessibilityLabel="Microphone level" style={{ height: 8, borderRadius: 4, backgroundColor: colors.muted, overflow: "hidden" }}>
      <View style={{ width: `${value * 100}%`, height: "100%", borderRadius: 4, backgroundColor: active ? colors.danger : colors.border }} />
    </View>
  );
}

/**
 * Record a spoken answer or type it. With server transcription (STT_PROVIDER configured) the recording
 * is sent as it is. Without it, the recording is kept for replay and the learner types what they said
 * (the keyboard's dictation microphone works too); the answer is then labelled as typed, so nobody
 * pretends pronunciation was assessed.
 */
export function AnswerRecorder({
  onAnswer,
  busy,
  maxSeconds,
  serverStt,
  submitLabel = "Send answer",
}: {
  onAnswer: (answer: SpokenAnswer) => Promise<void>;
  busy?: boolean;
  maxSeconds?: number;
  serverStt: boolean;
  submitLabel?: string;
}) {
  const recorder = useAnswerRecorder();
  const [typing, setTyping] = useState(false);
  const [typed, setTyped] = useState("");
  const [pending, setPending] = useState<Recording | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const stopping = useRef(false);
  const recording = recorder.phase === "recording";

  async function stop() {
    if (stopping.current) return;
    stopping.current = true;
    try {
      const result = await recorder.stop();
      if (!result) return;
      if (serverStt && result.uri) {
        try {
          await onAnswer({ recording: result, transcript: null, source: null });
          return;
        } catch (err) {
          setNotice(
            err instanceof ApiError && err.code === "transcription_unavailable"
              ? "The recording couldn't be transcribed. Please type what you said — your recording is kept."
              : "Your answer wasn't sent. Type it below to send it with your recording.",
          );
        }
      }
      // Keep the recording either way: it is uploaded with the typed answer for replay.
      setPending(result);
      setTyping(true);
    } finally {
      stopping.current = false;
    }
  }

  // Stop automatically when the time limit for this answer is reached.
  const overTime = !!maxSeconds && recording && recorder.elapsed >= maxSeconds;
  useEffect(() => {
    if (overTime) void stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [overTime]);

  async function submitTyped() {
    const text = typed.trim();
    if (!text) return;
    try {
      await onAnswer({ recording: pending, transcript: text, source: "typed" });
      setTyped("");
      setPending(null);
      setTyping(false);
      setNotice(null);
    } catch {
      // Keep the typed answer for another try; the parent explains what went wrong.
    }
  }

  return (
    <View style={{ gap: 12 }}>
      {recorder.error ? <Notice tone="warning">{recorder.error}</Notice> : null}
      {!typing ? (
        <View style={{ gap: 12 }}>
          <LevelMeter level={recorder.level} active={recording} />
          <Row wrap>
            {recording ? (
              <Button title={serverStt ? "Stop & send" : "Stop"} icon={Square} variant="danger" disabled={busy} onPress={stop} />
            ) : (
              <Button title={busy ? "Sending…" : "Start recording"} icon={Mic} loading={recorder.phase === "requesting" || busy} onPress={() => recorder.start()} />
            )}
            <Text variant="small" tone="muted" style={{ fontVariant: ["tabular-nums"] }}>
              {formatDuration(recorder.elapsed)}
              {maxSeconds ? ` / ${formatDuration(maxSeconds)}` : ""}
            </Text>
          </Row>
          <Button title="Type instead" icon={Keyboard} variant="ghost" size="sm" disabled={recording || busy} onPress={() => setTyping(true)} style={{ alignSelf: "flex-start" }} />
          {recording ? <Text variant="small" tone="muted">Recording… speak naturally, then stop when you have finished your answer.</Text> : null}
        </View>
      ) : (
        <View style={{ gap: 10 }}>
          {notice ? <Notice tone="warning">{notice}</Notice> : null}
          {pending && !notice ? <Notice tone="primary">Your recording is saved. Type what you said so SI can analyse it — tip: the microphone key on your keyboard can dictate it for you.</Notice> : null}
          <Input value={typed} onChangeText={setTyped} multiline placeholder="Type your answer as you would say it…" accessibilityLabel="Your answer" />
          <Row wrap>
            <Button title={submitLabel} icon={Send} disabled={!typed.trim()} loading={busy} onPress={submitTyped} />
            {!pending ? <Button title="Record instead" icon={Mic} variant="ghost" onPress={() => setTyping(false)} /> : null}
          </Row>
        </View>
      )}
    </View>
  );
}
