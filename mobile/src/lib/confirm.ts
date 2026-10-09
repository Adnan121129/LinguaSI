import { Alert, Platform } from "react-native";

/** Ask before destructive actions (native alert on phones, the browser dialog in the web preview). */
export function confirmAction(title: string, message: string, onConfirm: () => void, confirmLabel = "Delete") {
  if (Platform.OS === "web") {
    if (globalThis.confirm?.(`${title}\n\n${message}`)) onConfirm();
    return;
  }
  Alert.alert(title, message, [
    { text: "Cancel", style: "cancel" },
    { text: confirmLabel, style: "destructive", onPress: onConfirm },
  ]);
}
