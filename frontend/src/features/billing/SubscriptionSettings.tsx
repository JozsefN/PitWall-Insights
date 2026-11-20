import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { profileError } from "../../data/api/profile.api";
import { useAuthSession } from "../auth/useAuthSession";
import { useLayoutsQuery } from "../../data/queries/layouts.queries";
import { CapabilityMark } from "../profile/CapabilityMark";
import {
  billingPlans, changeBilling, openBilling, useMembership,
  type BillingInterval, type Plan, type PlanCode,
} from "../../data/queries/billing.queries";

const huf = new Intl.NumberFormat("en-HU", { currency: "HUF", style: "currency", maximumFractionDigits: 0 });
const aiTools: Record<string, string> = {
  session_summary: "session summary",
  driver_comparison: "driver comparison",
  session_questions: "session Q&A",
  replay_lap_summary: "replay lap summary",
};

const comparison: Array<{ label: string; value: (plan: Plan) => boolean | string | number }> = [
  { label: "Full Replay and Lookback", value: () => true },
  { label: "Telemetry, timing and race updates", value: () => true },
  { label: "Engineering and strategy models", value: plan => plan.level >= 1 },
  { label: "Model detection filters", value: plan => plan.level >= 1 },
  { label: "Saved layouts", value: plan => plan.saved_layouts },
  { label: "Panels per layout", value: plan => plan.panels_per_layout },
  { label: "AI responses per month (planned)", value: plan => plan.ai_monthly_planned === null ? "Unlimited" : plan.ai_monthly_planned || false },
  ...Object.entries(aiTools).map(([id, label]) => ({ label: `AI ${label} (planned)`, value: (plan: Plan) => Boolean(plan.ai_features_planned?.includes(id)) })),
];

export function SubscriptionSettings() {
  const client = useQueryClient();
  const { data: auth } = useAuthSession();
  const membership = useMembership();
  const layouts = useLayoutsQuery();
  const plans = useQuery({ queryKey: ["billing-plans"], queryFn: billingPlans, staleTime: 300_000 });
  const [params] = useSearchParams();
  const returned = params.get("checkout");
  const [interval, setInterval] = useState<BillingInterval>("month");
  const [selection, setSelection] = useState<PlanCode | null>(null);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const checkedReturn = useRef(false);
  const checkout = useMutation({ mutationFn: (plan: PlanCode) => openBilling("checkout", { plan, interval }) });
  const portal = useMutation({ mutationFn: () => openBilling("portal") });
  const change = useMutation({
    mutationFn: changeBilling,
    onSuccess: (value, action) => {
      if (action === "cancel") setConfirmCancel(false);
      client.setQueryData(["membership", auth?.user_id], value);
      void client.invalidateQueries({ queryKey: ["profile", auth?.user_id] });
    },
  });
  const { mutate: sync } = change;
  const current = membership.data;
  const selected = plans.data?.find(plan => plan.code === selection);
  const currentPrice = current?.interval ? current.plan.prices_huf[current.interval] : undefined;
  const paidUntil = current?.paid_until ? new Date(current.paid_until).toLocaleDateString(undefined, { dateStyle: "long" }) : null;
  const busy = checkout.isPending || portal.isPending || change.isPending;

  useEffect(() => {
    if (returned === "returned" && current?.has_customer && current.checkout_enabled && !checkedReturn.current) {
      checkedReturn.current = true;
      sync("sync");
    }
  }, [current?.checkout_enabled, current?.has_customer, returned, sync]);

  return <div className="subscription-settings">
    <section className="surface-card profile-section subscription-current" aria-label="Current subscription">
      <h2>{current ? `${current.plan.name} workspace` : "Your subscription"}</h2>
      {membership.isPending ? <p role="status">Loading your subscription…</p> : null}
      {membership.isError ? <p role="alert">Subscription status is unavailable. <button className="button-secondary" onClick={() => void membership.refetch()}>Retry</button></p> : null}
      {current ? <>
        <p>{layouts.data ? `${layouts.data.length} of ` : ""}{current.plan.saved_layouts} saved layouts · {current.plan.panels_per_layout} panels per layout</p>
        {currentPrice ? <p>{huf.format(currentPrice)} per {current.interval}</p> : null}
        {paidUntil ? <p>{current.cancel_at_period_end ? "Paid access ends" : "Next renewal"} {paidUntil}.</p> : null}
        {current.status && current.plan.code === "free" ? <p role="status">Billing status: {current.status.replaceAll("_", " ")}.</p> : null}
        {returned === "returned" && current.plan.code === "free" ? <p role="status">Checkout returned. Paid access appears after Stripe confirms the payment.</p> : null}
        {returned === "cancelled" ? <p role="status">You left the Stripe checkout.</p> : null}
        <div className="profile-actions">
          {current.has_customer && current.checkout_enabled ? <>
            {current.can_cancel && !confirmCancel ? <button className="button-secondary" onClick={() => setConfirmCancel(true)}>Stop renewal</button> : null}
            <button className="button-secondary" onClick={() => portal.mutate()} disabled={busy}>Billing details & invoices</button>
            <button className="button-secondary" onClick={() => change.mutate("sync")} disabled={busy}>Refresh status</button>
          </> : null}
        </div>
        {confirmCancel ? <div className="subscription-confirmation">
          <p>{paidUntil ? `Keep paid access through ${paidUntil}. Your subscription will stop renewing.` : "Your subscription will stop renewing."}</p>
          <div className="profile-actions"><button className="button-primary" disabled={busy} onClick={() => change.mutate("cancel")}>Confirm stop renewal</button><button className="button-secondary" disabled={busy} onClick={() => setConfirmCancel(false)}>Keep renewal</button></div>
        </div> : null}
        {!current.checkout_enabled ? <p className="profile-help">To enable test checkout, configure a Stripe Sandbox key, webhook signing secret, and four recurring test prices in <code>backend/.env</code>, then restart the API.</p> : null}
      </> : null}
      {(change.error ?? portal.error) ? <p role="alert">{profileError(change.error ?? portal.error)}</p> : null}
    </section>
    <section className="surface-card profile-section" aria-labelledby="subscription-plans">
      <div className="profile-section-heading">
        <div><h2 id="subscription-plans">Compare plans</h2><p>Choose the tools and layout space you need for race weekends.</p></div>
        <div className="profile-tabs" aria-label="Billing interval">
          <button type="button" aria-pressed={interval === "month"} onClick={() => setInterval("month")}>Monthly</button>
          <button type="button" aria-pressed={interval === "year"} onClick={() => setInterval("year")}>Annual · 2 months saved</button>
        </div>
      </div>
      {plans.isError ? <p role="alert">Plans could not be loaded.</p> : null}
      {plans.data ? <div className="profile-comparison-scroll" tabIndex={0} role="region" aria-label="Subscription plan comparison">
        <table className="profile-comparison subscription-table">
          <thead><tr><th scope="col">Feature</th>{plans.data.map(plan => <th scope="col" key={plan.code} data-current={plan.code === current?.plan.code}>
            <strong>{plan.name}</strong><span className="subscription-price">{huf.format(plan.prices_huf[interval] ?? 0)}{plan.code !== "free" ? <small> / {interval}</small> : null}</span>
          </th>)}</tr></thead>
          <tbody>{comparison.map(row => <tr key={row.label}>
            <th scope="row">{row.label}</th>{plans.data.map(plan => {
              const value = row.value(plan);
              return <td key={plan.code} data-current={plan.code === current?.plan.code}>{typeof value === "boolean" ? <CapabilityMark included={value} /> : value}</td>;
            })}
          </tr>)}</tbody>
          <tfoot><tr><th scope="row">Select a plan</th>{plans.data.map(plan => <td key={plan.code} data-current={plan.code === current?.plan.code}>
            {current?.plan.code === plan.code ? <span className="profile-badge">Current plan</span> : plan.code !== "free" ?
              <button type="button" className="button-secondary" disabled={!current?.checkout_enabled || Boolean(current.status) || busy} onClick={() => { checkout.reset(); setSelection(plan.code); }}>Choose {plan.name}</button> : <span className="profile-help">Base access</span>}
          </td>)}</tr></tfoot>
        </table>
      </div> : null}
      {selected ? <section className="surface-card profile-section subscription-confirmation" aria-label="Confirm test subscription">
        <h3>Subscribe to {selected.name}</h3>
        <p>{huf.format(selected.prices_huf[interval] ?? 0)} every {interval}, billed in full. Renewal continues until you stop it in this profile. The Stripe test page collects your billing name, address and test card. No real payment is taken.</p>
        <div className="profile-actions"><button className="button-primary" disabled={busy || Boolean(current?.status)} onClick={() => checkout.mutate(selected.code)}>Continue to test checkout</button><button className="button-secondary" disabled={busy} onClick={() => setSelection(null)}>Back to plans</button></div>
        {checkout.isError ? <p role="alert">{profileError(checkout.error)}</p> : null}
      </section> : null}
    </section>
  </div>;
}
