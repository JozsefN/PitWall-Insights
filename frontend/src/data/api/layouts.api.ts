import { apiClient } from "./client";
import type { LayoutDto, LayoutMutationDto } from "../contracts/layouts.contracts";

export async function listLayouts(): Promise<LayoutDto[]> {
  const { data } = await apiClient.get("/api/layouts");
  return data;
}

export async function createLayout(payload: LayoutMutationDto): Promise<LayoutDto> {
  const { data } = await apiClient.post("/api/layouts", payload);
  return data;
}

export async function updateLayout(
  layoutId: string,
  payload: Partial<LayoutMutationDto>,
): Promise<LayoutDto> {
  const { data } = await apiClient.put(`/api/layouts/${layoutId}`, payload);
  return data;
}

export async function deleteLayout(layoutId: string): Promise<void> {
  await apiClient.delete(`/api/layouts/${layoutId}`);
}
