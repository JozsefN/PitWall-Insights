import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import { useAuthSession } from "../features/auth/useAuthSession";
import { getProfile, getDataCapabilities, profileError, updateProfile } from "../data/api/profile.api";
import type { Profile } from "../data/contracts/profile.contracts";
import "./profile.css";

function ProfileDetails({ profile }: { profile: Profile }) {
  const client = useQueryClient();
  const [name, setName] = useState(profile.name ?? "");
  const [nickname, setNickname] = useState(profile.nickname ?? "");
  const [phone, setPhone] = useState(profile.phone_number ?? "");
  const save = useMutation({ mutationFn: updateProfile, onSuccess: () => client.invalidateQueries({ queryKey: ["profile"] }) });
  return <section className="surface-card profile-section">
    <div className="profile-section-heading"><div><h2>Your details</h2><p>Choose how you appear in your workspace.</p></div></div>
    <form onSubmit={event => { event.preventDefault(); save.mutate({ name: name || null, nickname: nickname || null, phone_number: phone || null }); }}>
      <div className="profile-fields"><label>Display name<input value={name} onChange={e => setName(e.target.value)} maxLength={120} autoComplete="name" /></label>
        <label>Nickname<input value={nickname} onChange={e => setNickname(e.target.value)} maxLength={60} autoComplete="nickname" /></label></div>
      <details className="profile-secondary"><summary>Contact information <span>Optional</span></summary><p className="profile-help">Not needed to explore sessions. Billing details will be requested separately if checkout becomes available.</p>
        <label>Phone number<input type="tel" value={phone} onChange={e => setPhone(e.target.value)} maxLength={32} autoComplete="tel" /></label>
      </details>
      <div className="profile-actions"><button className="button-secondary" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save details"}</button>
        {save.isSuccess && <span role="status">Details saved</span>}
        {save.isError && <p role="alert">{profileError(save.error)}</p>}</div>
    </form>
  </section>;
}

export function ProfilePage() {
  const { data: auth } = useAuthSession();
  const location = useLocation();
  const [tab, setTab] = useState<"profile" | "data">(() => new URLSearchParams(location.search).get("tab") === "data" ? "data" : "profile");
  const capabilities = useQuery({ queryKey: ["data-capabilities"], queryFn: getDataCapabilities, enabled: tab === "data", staleTime: 300_000 });
  const profile = useQuery({ queryKey: ["profile", auth?.user_id], queryFn: getProfile, enabled: Boolean(auth?.authenticated), staleTime: 60_000 });
  return <div className="profile-page">
    <header className="profile-header"><span className="ui-pill ui-pill--focus">Your paddock</span><h1 className="display-font">Your profile</h1><p>Your identity and access to historical race analysis.</p></header>
    <nav className="profile-tabs" aria-label="Profile sections"><button type="button" aria-pressed={tab === "profile"} onClick={() => setTab("profile")}>Profile</button><button type="button" aria-pressed={tab === "data"} onClick={() => setTab("data")}>Data availability</button></nav>
    {tab === "data" && <section className="surface-card profile-section"><h2>Explore with OpenF1</h2><p className="profile-help">Historical sessions from 2023. No external account or subscription needed. Individual sessions can have gaps.</p>
      {capabilities.isPending && <p role="status">Loading data availability...</p>}
      {capabilities.isError && <p role="alert">{profileError(capabilities.error)}</p>}
      {capabilities.data && <><div className="profile-comparison-scroll"><table className="profile-comparison"><thead><tr><th>Information</th><th>Availability</th></tr></thead><tbody>{capabilities.data.features.map(row => <tr key={row.feature}><th scope="row">{row.feature}<small>{row.note}</small></th><td><span className={`profile-availability ${row.supported ? "is-supported" : "is-unavailable"}`} aria-label={row.supported ? "Supported" : "Unavailable"}><span aria-hidden="true">{row.supported ? "✓" : "✕"}</span><span className="profile-check-label">{row.supported ? "Supported" : "Unavailable"}</span></span></td></tr>)}</tbody></table></div><p className="profile-help">{capabilities.data.note}</p></>}
    </section>}
    {profile.isPending && <p role="status">Loading your profile...</p>}
    {profile.isError && <p role="alert">{profileError(profile.error)}</p>}
    {profile.data && tab === "profile" && <div className="profile-grid"><div className="profile-main"><ProfileDetails key={profile.data.user_id} profile={profile.data} /></div>
      <aside className="surface-card profile-membership"><span className="profile-badge">Free workspace</span><h2>Your account</h2><dl><dt>Account</dt><dd>{profile.data.email}</dd><dt>Data source</dt><dd>OpenF1 history</dd><dt>Coverage</dt><dd>2023 onwards</dd></dl><p className="profile-help">Session telemetry, historical replay and analysis use OpenF1. Live race streaming is currently unavailable.</p></aside></div>}
  </div>;
}
