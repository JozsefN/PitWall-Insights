import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { useAuthSessionQuery } from "./auth.queries";

export type PlanCode = "free" | "analyst" | "pro";
export type BillingInterval = "month" | "year";
export type Plan = {
  code: PlanCode;
  name: string;
  level: number;
  saved_layouts: number;
  panels_per_layout: number;
  ai_monthly_planned: number | null;
  ai_features_planned: string[];
  prices_huf: Partial<Record<BillingInterval, number>>;
};

export type Membership = {
  plan: Plan;
  subscription_plan: PlanCode | null;
  interval: BillingInterval | null;
  status: string | null;
  paid_until: string | null;
  cancel_at_period_end: boolean;
  can_cancel: boolean;
  has_customer: boolean;
  checkout_enabled: boolean;
  ai_available: boolean;
};

export function useMembership() {
  const { data: session } = useAuthSessionQuery();
  return useQuery({
    queryKey: ["membership", session?.user_id],
    queryFn: async ({ signal }) => (await apiClient.get<Membership>("/api/billing/me", { signal })).data,
    enabled: Boolean(session?.user_id),
    refetchInterval: 30_000,
  });
}

export const billingPlans = async () => (await apiClient.get<Plan[]>("/api/billing/plans")).data;

export async function openBilling(action: "checkout" | "portal", selection?: { plan: PlanCode; interval: BillingInterval }) {
  const { data } = await apiClient.post<{ url: string }>(`/api/billing/${action}`, selection);
  window.location.assign(data.url);
}

export async function changeBilling(action: "sync" | "cancel") {
  return (await apiClient.post<Membership>(`/api/billing/${action}`)).data;
}
