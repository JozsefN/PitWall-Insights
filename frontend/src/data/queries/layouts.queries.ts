import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createLayout,
  deleteLayout,
  listLayouts,
  updateLayout,
} from "../api/layouts.api";
import type { LayoutMutationDto } from "../contracts/layouts.contracts";
import { useAuthSessionQuery as useAuthSession } from "./auth.queries";
import { listLayoutFavorites, setLayoutFavorite } from "../api/layouts.api";

export function useLayoutsQuery(enabled = true) {
  const auth = useAuthSession();
  return useQuery({
    queryKey: ["layouts", auth.data?.user_id ?? auth.data?.email],
    queryFn: listLayouts,
    enabled: enabled && auth.data?.authenticated === true,
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
    mutationFn: ({
      layoutId,
      payload,
    }: {
      layoutId: string;
      payload: Partial<LayoutMutationDto>;
    }) => updateLayout(layoutId, payload),
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
      queryClient.invalidateQueries({ queryKey: ["layout-favorites"] });
    },
  });
}

export function useLayoutFavoritesQuery() {
  const auth = useAuthSession();
  return useQuery({
    queryKey: ["layout-favorites", auth.data?.user_id ?? auth.data?.email],
    queryFn: listLayoutFavorites,
    enabled: auth.data?.authenticated === true,
  });
}

export function useSetLayoutFavoriteMutation() {
  const queryClient = useQueryClient();
  const auth = useAuthSession();
  return useMutation({
    mutationFn: setLayoutFavorite,
    onSuccess: (data) =>
      queryClient.setQueryData(
        ["layout-favorites", auth.data?.user_id ?? auth.data?.email],
        data,
      ),
  });
}
