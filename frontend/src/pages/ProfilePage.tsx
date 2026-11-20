import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { SubscriptionSettings } from "../features/billing/SubscriptionSettings";
import { GoogleConnection } from "../features/auth/GoogleConnection";
import { CapabilityMark } from "../features/profile/CapabilityMark";
import { useMembership } from "../data/queries/billing.queries";
import { useAuthSession } from "../features/auth/useAuthSession";
import { getProfile, getDataCapabilities, profileError, updateProfile } from "../data/api/profile.api";
import type { Profile } from "../data/contracts/profile.contracts";
import "./profile.css";

function ProfileDetails({ profile }: { profile: Profile }) {
  const client = useQueryClient();
  const [name, setName] = useState(profile.name ?? "");
  const [nickname, setNickname] = useState(profile.nickname ?? "");
  const [phone, setPhone] = useState(profile.phone_number ?? "");
  const save = useMutation({ mutationFn: updateProfile, onSuccess: () => client.invalidateQueries({ queryKey: ["profile", profile.user_id] }) });

  return <section className="surface-card profile-section">
    <div className="profile-section-heading"><div><h2>Driver profile</h2><p>Set the name you use in your PitWall workspace.</p></div></div>
    <form onSubmit={event => { event.preventDefault(); save.mutate({ name: name || null, nickname: nickname || null, phone_number: phone || null }); }}>
      <div className="profile-fields"><label>Display name<input value={name} onChange={e => setName(e.target.value)} maxLength={120} autoComplete="name" /></label>
        <label>Nickname<input value={nickname} onChange={e => setNickname(e.target.value)} maxLength={60} autoComplete="nickname" /></label></div>
      <details className="profile-secondary"><summary>Contact information <small>Optional</small></summary><p className="profile-help">Contact details for your PitWall profile.</p>
        <label>Phone number<input type="tel" value={phone} onChange={e => setPhone(e.target.value)} maxLength={32} autoComplete="tel" /></label>
      </details>
      <div className="profile-actions"><button className="button-primary" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save details"}</button>
        {save.isSuccess && <span role="status">Details saved</span>}
        {save.isError && <p role="alert">{profileError(save.error)}</p>}</div>
    </form>
  </section>;
}

function DataAvailability() {
  const capabilities = useQuery({ queryKey: ["data-capabilities"], queryFn: getDataCapabilities, staleTime: 300_000 });
  return <section className="surface-card profile-section">
    <div className="profile-section-heading"><div><h2>OpenF1 coverage</h2><p>Compare the data available for historical sessions from 2023 onwards.</p></div></div>
    {capabilities.isPending ? <p role="status">Loading data availability…</p> : null}
    {capabilities.isError ? <p role="alert">{profileError(capabilities.error)}</p> : null}
    {capabilities.data ? <>
      <div className="profile-comparison-scroll"><table className="profile-comparison"><thead><tr><th scope="col">Information</th><th scope="col">Availability</th></tr></thead>
        <tbody>{capabilities.data.features.map(row => <tr key={row.feature}><th scope="row">{row.feature}<small>{row.note}</small></th><td><CapabilityMark included={row.supported} showLabel /></td></tr>)}</tbody>
      </table></div>
      <p className="profile-help">{capabilities.data.note}</p>
    </> : null}
  </section>;
}

const profileTabs = [["profile", "Profile"], ["subscription", "Subscription"], ["data", "Data availability"]] as const;

export function ProfilePage() {
  const { data: auth } = useAuthSession();
  const [params, setParams] = useSearchParams();
  const tab = profileTabs.find(([id]) => id === params.get("tab"))?.[0] ?? "profile";
  const membership = useMembership();
  const profile = useQuery({ queryKey: ["profile", auth?.user_id], queryFn: getProfile, enabled: Boolean(auth?.user_id && tab === "profile"), staleTime: 60_000 });
  const planName = membership.data?.plan.name;
  const admin = auth?.role === "admin";

  return <div className="profile-page">
    <header className="feature-banner profile-hero">
      <div><h1 className="feature-banner__title">Your profile</h1><p className="feature-banner__detail">Manage your account, sign-in methods, and race workspace.</p></div>
      <div className="profile-hero__status">
        {planName ? <span className="profile-badge">{planName} workspace</span> : null}
        {admin ? <span className="profile-badge profile-badge--admin">Administrator</span> : null}
      </div>
    </header>
    <nav className="profile-tabs" aria-label="Profile sections">
      {profileTabs.map(([id, label]) => <button type="button" key={id} aria-current={tab === id ? "page" : undefined} aria-pressed={tab === id} onClick={() => setParams(id === "profile" ? {} : { tab: id })}>{label}</button>)}
    </nav>
    {tab === "subscription" ? <SubscriptionSettings /> : null}
    {tab === "data" ? <DataAvailability /> : null}
    {tab === "profile" ? <>
      {profile.isPending ? <p role="status">Loading your profile…</p> : null}
      {profile.isError ? <p role="alert">{profileError(profile.error)}</p> : null}
      {profile.data ? <div className="profile-grid">
        <div className="profile-main"><ProfileDetails key={profile.data.user_id} profile={profile.data} /><GoogleConnection key={profile.data.user_id} /></div>
        <aside className="surface-card profile-section profile-membership">
          <h2>Account access</h2>
          <dl><dt>Email</dt><dd>{profile.data.email}</dd>
            {profile.data.email_verified ? <><dt>Email status</dt><dd>Verified</dd></> : null}
            <dt>Role</dt><dd>{admin ? "Administrator" : "Member"}</dd>
            <dt>Plan</dt><dd>{planName ?? profile.data.subscription.plan}</dd>
          </dl>
          <Link className="button-secondary" to={admin ? "/system/health" : "/sessions?view=explorer"}>{admin ? "Open system health" : "Browse sessions"}</Link>
        </aside>
      </div> : null}
    </> : null}
  </div>;
}
