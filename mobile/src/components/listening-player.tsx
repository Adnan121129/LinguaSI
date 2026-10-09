import { createAudioPlayer, type AudioPlayer } from "expo-audio";
import { Headphones, Pause, Play, RotateCcw } from "lucide-react-native";
import { useEffect, useRef, useState } from "react";
import { View } from "react-native";

import { Button, Notice, Row, Text } from "@/components/ui";
import { authHeaders, mediaUrl } from "@/lib/api";
import { assignVoices, loadVoices, speak, stopSpeaking, type SpeakerVoice } from "@/lib/speech";
import { useTheme } from "@/lib/theme";

export type PlayerSegment = { speaker: string; text: string | null; audio_url?: string | null };

/** Play one server audio file and resolve when it ends (or fails). */
function playFile(path: string, rate: number, register: (player: AudioPlayer | null) => void): Promise<void> {
  return new Promise((resolve) => {
    const player = createAudioPlayer({ uri: mediaUrl(path) ?? undefined, headers: authHeaders() });
    register(player);
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      subscription.remove();
      player.remove();
      register(null);
      resolve();
    };
    const subscription = player.addListener("playbackStatusUpdate", (status) => {
      if (status.didJustFinish) finish();
    });
    player.setPlaybackRate(rate);
    player.play();
    // Never hang if the file can't load: give up after its length plus a margin.
    setTimeout(finish, 180_000);
  });
}

/**
 * Plays a listening script: server-generated audio when the server has a TTS provider, otherwise the
 * phone's own voices (a different voice per speaker). The transcript stays hidden until submission.
 */
export function ListeningPlayer({
  segments,
  speakers,
  rate = 1,
  mode,
  maxPlays,
  onPlay,
}: {
  segments: PlayerSegment[];
  speakers: (SpeakerVoice & { name?: string; role?: string })[];
  rate?: number;
  mode: "server" | "device";
  maxPlays?: number;
  onPlay?: (count: number) => void;
}) {
  const { colors } = useTheme();
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState<number | null>(null);
  const [plays, setPlays] = useState(0);
  const cancelled = useRef(false);
  const active = useRef<AudioPlayer | null>(null);

  useEffect(
    () => () => {
      cancelled.current = true;
      stopSpeaking();
      active.current?.remove();
    },
    [],
  );

  async function play() {
    if (playing) return;
    cancelled.current = false;
    setPlaying(true);
    const count = plays + 1;
    setPlays(count);
    onPlay?.(count);
    const voices = mode === "device" ? assignVoices(await loadVoices(), speakers) : {};
    for (let i = 0; i < segments.length; i++) {
      if (cancelled.current) break;
      setCurrent(i);
      const seg = segments[i];
      if (mode === "server" && seg.audio_url) await playFile(seg.audio_url, rate, (p) => (active.current = p));
      else if (seg.text) await speak(seg.text, { voice: voices[seg.speaker], rate });
      await new Promise((r) => setTimeout(r, 250));
    }
    setCurrent(null);
    setPlaying(false);
  }

  function stop() {
    cancelled.current = true;
    stopSpeaking();
    active.current?.pause();
    setPlaying(false);
    setCurrent(null);
  }

  const speaker = current !== null ? speakers.find((s) => s.id === segments[current]?.speaker) : null;
  return (
    <View style={{ gap: 12 }}>
      <Row gap={12}>
        <View style={{ width: 52, height: 52, borderRadius: 26, alignItems: "center", justifyContent: "center", backgroundColor: playing ? colors.primary : colors.primarySoft }}>
          <Headphones size={24} color={playing ? colors.primaryForeground : colors.primary} />
        </View>
        <View style={{ flex: 1, gap: 2 }}>
          <Text weight="600">{playing ? (speaker?.name ? `${speaker.name} is speaking…` : "Playing…") : plays ? `Played ${plays} time${plays === 1 ? "" : "s"}` : "Ready to play"}</Text>
          <Text variant="caption" tone="muted">
            {segments.length} parts · {mode === "server" ? "studio voices" : "your device's voices"}
          </Text>
        </View>
      </Row>
      {current !== null ? (
        <View style={{ height: 6, borderRadius: 3, backgroundColor: colors.muted, overflow: "hidden" }}>
          <View style={{ width: `${((current + 1) / segments.length) * 100}%`, height: "100%", backgroundColor: colors.primary }} />
        </View>
      ) : null}
      <Row wrap>
        {playing ? (
          <Button title="Stop" icon={Pause} variant="outline" onPress={stop} />
        ) : (
          <Button title={plays ? "Play again" : "Play recording"} icon={plays ? RotateCcw : Play} disabled={!!maxPlays && plays >= maxPlays} onPress={play} />
        )}
        {maxPlays ? <Text variant="caption" tone="muted">{Math.max(0, maxPlays - plays)} of {maxPlays} plays left</Text> : null}
      </Row>
      {mode === "device" ? <Notice tone="muted">No sound? Check the silent switch and volume. The transcript appears after you submit.</Notice> : null}
    </View>
  );
}
