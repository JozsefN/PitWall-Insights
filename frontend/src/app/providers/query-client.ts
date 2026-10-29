import { QueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: (count, error) =>
          !(isAxiosError(error) && error.response?.status === 401) && count < 1,
        refetchOnWindowFocus: false,
        staleTime: 15_000,
      },
      mutations: {
        retry: 0,
      },
    },
  });
}
