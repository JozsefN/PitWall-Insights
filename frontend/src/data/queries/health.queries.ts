import { useQuery } from "@tanstack/react-query";
import { getApiHealth, getRootHealth } from "../api/health.api";

export function useRootHealthQuery() {
  return useQuery({
    queryKey: ["health", "root"],
    queryFn: getRootHealth,
  });
}

export function useApiHealthQuery() {
  return useQuery({
    queryKey: ["health", "api"],
    queryFn: getApiHealth,
  });
}