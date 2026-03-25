import { DashboardRenderer } from "../widgets/shared/DashboardRenderer";
import { homeDashboardConfig } from "../widgets/registry/dashboard.config";

export function HomePage() {
  return <DashboardRenderer config={homeDashboardConfig} />;
}