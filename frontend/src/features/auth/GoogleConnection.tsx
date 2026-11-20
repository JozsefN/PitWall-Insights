import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../data/api/client";
import { useGoogleConfig } from "../../data/queries/google.queries";
import { GoogleSignIn } from "./GoogleSignIn";
import { useAuthSession } from "./useAuthSession";

export function GoogleConnection() {
  const client = useQueryClient();
  const { data: session } = useAuthSession();
  const config = useGoogleConfig();
  const [password, setPassword] = useState("");
  const key = ["google-connection", session?.user_id];
  const connection = useQuery({
    queryKey: key,
    queryFn: async () => (await apiClient.get<{ linked: boolean }>("/api/auth/google/connection")).data,
    enabled: Boolean(session?.user_id),
  });

  return <section className="surface-card profile-section">
    <div className="profile-section-heading">
      <div><h2>Sign-in methods</h2><p>Manage how you enter your PitWall account.</p></div>
      {connection.data?.linked ? <span className="profile-badge">Google linked</span> : null}
    </div>
    {connection.isPending ? <p role="status" className="profile-help">Checking your Google connection…</p> : null}
    {connection.isError ? <p role="alert">Google connection status could not be loaded.</p> : null}
    {connection.data?.linked ? <p className="profile-help">Google is linked to this account.{config.data?.enabled === false ? " Google sign-in is awaiting setup on this server." : ""}</p> : null}
    {connection.data?.linked === false ? <>
      <p className="profile-help">Connect a Google account for a quicker sign-in.</p>
      {config.data?.enabled ? <div className="profile-fields"><label>Current PitWall password
        <input type="password" autoComplete="current-password" maxLength={128} value={password} onChange={event => setPassword(event.target.value)} />
      </label></div> : null}
      <div className="profile-actions"><GoogleSignIn action="link" password={password} onResult={(result) => {
        if (result.status === "authenticated") {
          setPassword("");
          client.setQueryData(key, { linked: true });
        }
      }} /></div>
    </> : null}
  </section>;
}
