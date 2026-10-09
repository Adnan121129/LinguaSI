import { useAudioPlayer, useAudioPlayerStatus } from "expo-audio";
import { Pause, Play } from "lucide-react-native";

import { Button } from "@/components/ui";
import { authHeaders, mediaUrl } from "@/lib/api";

/** Play / pause a stored recording or generated audio served by the API (authenticated). */
export function AudioButton({ path, label = "Play recording" }: { path: string; label?: string }) {
  const player = useAudioPlayer({ uri: mediaUrl(path) ?? undefined, headers: authHeaders() });
  const status = useAudioPlayerStatus(player);
  const playing = status.playing;
  return (
    <Button
      title={playing ? "Pause" : status.didJustFinish || status.currentTime === 0 ? label : "Resume"}
      icon={playing ? Pause : Play}
      size="sm"
      variant="outline"
      onPress={() => {
        if (playing) {
          player.pause();
          return;
        }
        if (status.duration > 0 && status.currentTime >= status.duration - 0.05) player.seekTo(0);
        player.play();
      }}
      style={{ alignSelf: "flex-start" }}
    />
  );
}
