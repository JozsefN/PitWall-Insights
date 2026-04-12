import type { DashboardAudience, DashboardConfig } from "../../widgets/registry/widget.types";

export interface LayoutDto {
  id: string;
  name: string;
  description: string | null;
  source: "user";
  audience: DashboardAudience;
  schemaVersion: number;
  config: DashboardConfig;
  createdAt: string;
  updatedAt: string;
}

export interface LayoutMutationDto {
  name: string;
  description?: string | null;
  audience: DashboardAudience;
  schemaVersion: number;
  config: DashboardConfig;
}
