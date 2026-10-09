import { Segmented } from "@/components/ui";
import { useUpdateProfile } from "@/hooks/use-me";
import { useTheme, type ThemePreference } from "@/lib/theme";

/** Light / Dark / System. Applies instantly, is saved on the device and synced to the learner profile. */
export function ThemeToggle() {
  const { preference, setPreference } = useTheme();
  const update = useUpdateProfile();
  return (
    <Segmented<ThemePreference>
      value={preference}
      onChange={(value) => {
        setPreference(value);
        update.mutate({ theme: value });
      }}
      options={[
        { value: "light", label: "Light" },
        { value: "dark", label: "Dark" },
        { value: "system", label: "System" },
      ]}
    />
  );
}
