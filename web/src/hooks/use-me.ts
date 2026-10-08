"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Profile, User } from "@/lib/types";

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => api<User>("/me"), staleTime: 60_000 });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (changes: Partial<Profile> & { name?: string; clear_test_date?: boolean }) => api<User>("/me", { method: "PATCH", json: changes }),
    onSuccess: (user) => {
      queryClient.setQueryData(["me"], user);
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
