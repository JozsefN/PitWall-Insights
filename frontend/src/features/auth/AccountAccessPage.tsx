import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { getAuthSession, login, resendCode, signup, verifyEmail } from "../../data/api/auth.api";
import { profileError } from "../../data/api/profile.api";
import type { AuthResult, VerificationRequired } from "../../data/contracts/auth.contracts";
import { useAuthConfigQuery } from "../../data/queries/auth.queries";
import { getAuthRedirectPath } from "./auth-redirect";
import { GoogleSignIn } from "./GoogleSignIn";
import "./account-access.css";

export function AccountAccessPage({ mode }: { mode: "signin" | "signup" }) {
  const signingUp = mode === "signup";
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const config = useAuthConfigQuery();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [challenge, setChallenge] = useState<VerificationRequired>();
  const [code, setCode] = useState("");

  async function handleResult(result: AuthResult) {
    setPassword("");
    if (result.status === "verification_required") {
      setCode("");
      setChallenge(result);
      return;
    }
    localStorage.setItem("auth_token", result.access_token);
    await queryClient.cancelQueries({ queryKey: ["auth-session"] });
    await queryClient.fetchQuery({ queryKey: ["auth-session"], queryFn: getAuthSession, staleTime: 0 });
    navigate(getAuthRedirectPath(location.state), { replace: true });
  }

  const credentials = useMutation({ mutationFn: signingUp ? signup : login, onSuccess: handleResult });
  const verify = useMutation({ mutationFn: verifyEmail, onSuccess: handleResult });
  const resend = useMutation({ mutationFn: resendCode, onSuccess: handleResult });
  const issue = challenge ? verify.error ?? resend.error : credentials.error;
  const emailUnavailable = !challenge && signingUp && config.data?.email_verification_available === false;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (challenge) verify.mutate({ challenge_id: challenge.challenge_id, code });
    else credentials.mutate({ email, password });
  }

  return (
    <div className="account-access">
      <section className="account-access__card surface-card" aria-labelledby="account-access-title">
        <header className="account-access__heading">
          <h1 id="account-access-title" className="display-font">
            {challenge ? "Verify your email" : signingUp ? "Create account" : "Sign in"}
          </h1>
          <p>{challenge
            ? <>Enter the six-digit code sent to <strong>{challenge.email}</strong>.</>
            : signingUp ? "Set up your workspace for race replay and telemetry." : "Pick up where you left off in the race archive."}</p>
        </header>
        {!challenge ? <div className="account-access__federated"><GoogleSignIn onResult={handleResult} /><div className="account-access__divider">or use email</div></div> : null}
        <form className="account-access__form" onSubmit={submit}>
          {challenge ? (
            <label>Verification code<input autoFocus autoComplete="one-time-code" inputMode="numeric" pattern="[0-9]{6}" maxLength={6}
              value={code} onChange={event => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))} required /></label>
          ) : <>
            <label>Email<input type="email" autoComplete="email" maxLength={255} value={email} onChange={event => setEmail(event.target.value)} required /></label>
            <label>Password<input type="password" autoComplete={signingUp ? "new-password" : "current-password"} minLength={8} maxLength={128}
              value={password} onChange={event => setPassword(event.target.value)} required /></label>
          </>}
          {emailUnavailable ? <p className="account-access__help">Email signup is awaiting mail setup on this server.</p> : null}
          {issue ? <p role="alert" className="account-access__error">{profileError(issue)}</p> : null}
          {resend.isSuccess && challenge ? <p role="status" className="account-access__help">A new code is on its way.</p> : null}
          <button type="submit" className="button-primary" disabled={emailUnavailable || credentials.isPending || verify.isPending || resend.isPending}>
            {challenge ? "Verify and continue" : credentials.isPending ? "Working…" : signingUp ? "Send verification code" : "Sign in"}
          </button>
        </form>
        {challenge ? <div className="account-access__links">
          <button className="button-secondary" type="button" disabled={resend.isPending || verify.isPending} onClick={() => { verify.reset(); resend.mutate(challenge.challenge_id); }}>Resend code</button>
          <button className="button-secondary" type="button" disabled={resend.isPending || verify.isPending} onClick={() => { setChallenge(undefined); setCode(""); resend.reset(); verify.reset(); }}>Start over</button>
        </div> : <p className="account-access__help">{signingUp ? "Already have an account? " : "New to PitWall? "}<Link to={signingUp ? "/login" : "/signup"} state={location.state}>{signingUp ? "Sign in" : "Create an account"}</Link></p>}
      </section>
    </div>
  );
}
