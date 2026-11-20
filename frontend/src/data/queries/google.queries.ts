import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";

export function useGoogleConfig() {
  return useQuery({
    queryKey: ["google-config"],
    queryFn: async () => (await apiClient.get<{ enabled: boolean }>("/api/auth/google/config")).data,
    staleTime: 60_000,
  });
}
