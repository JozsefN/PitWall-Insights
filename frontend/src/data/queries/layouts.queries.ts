import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createLayout, deleteLayout, listLayouts, updateLayout } from "../api/layouts.api";
import type { LayoutMutationDto } from "../contracts/layouts.contracts";

export function useLayoutsQuery(enabled = true) {
  return useQuery({
    queryKey: ["layouts"],
    queryFn: listLayouts,
    enabled,
  });
}

export function useCreateLayoutMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: LayoutMutationDto) => createLayout(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["layouts"] });
    },
  });
}

export function useUpdateLayoutMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ layoutId, payload }: { layoutId: string; payload: Partial<LayoutMutationDto> }) =>
      updateLayout(layoutId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["layouts"] });
    },
  });
}

export function useDeleteLayoutMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (layoutId: string) => deleteLayout(layoutId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["layouts"] });
    },
  });
}
