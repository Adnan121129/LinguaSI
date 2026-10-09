import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Profile, User } from "@/lib/types";

export function useMe() {
  const { status } = useAuth();
  return useQuery({ queryKey: ["me"], queryFn: () => api<User>("/me"), enabled: status === "signedIn", staleTime: 60_000 });
}

export type ProfileChanges = Partial<Profile> & { name?: string; clear_test_date?: boolean };

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (changes: ProfileChanges) => api<User>("/me", { method: "PATCH", json: changes }),
    onSuccess: (user) => {
      queryClient.setQueryData(["me"], user);
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
