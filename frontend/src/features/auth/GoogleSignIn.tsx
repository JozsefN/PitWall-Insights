import { useEffect, useRef, useState } from "react";
import { apiClient } from "../../data/api/client";
import { profileError } from "../../data/api/profile.api";
import type { AuthResult } from "../../data/contracts/auth.contracts";
import { useGoogleConfig } from "../../data/queries/google.queries";

type GoogleClient = {
  initialize: (config: { client_id: string; nonce: string; callback: (result: { credential: string }) => void }) => void;
  renderButton: (target: HTMLElement, config: { theme: string; size: string; text: string; width: number }) => void;
};

function googleClient() {
  return (window as Window & { google?: { accounts?: { id?: GoogleClient } } }).google?.accounts?.id;
}

let scriptLoad: Promise<GoogleClient> | undefined;
function loadGoogle() {
  const loaded = googleClient();
  if (loaded) return Promise.resolve(loaded);
  if (scriptLoad) return scriptLoad;
  scriptLoad = new Promise<GoogleClient>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.onload = () => {
      const sdk = googleClient();
      if (sdk) resolve(sdk);
      else reject(new Error("Google sign-in did not load."));
    };
    script.onerror = () => { script.remove(); reject(new Error("Google sign-in did not load.")); };
    document.head.append(script);
  }).catch((error: unknown) => {
    scriptLoad = undefined;
    throw error;
  });
  return scriptLoad;
}

export function GoogleSignIn({ action = "signin", password, onResult }: {
  action?: "signin" | "link";
  password?: string;
  onResult: (result: AuthResult) => void | Promise<void>;
}) {
  const config = useGoogleConfig();
  const target = useRef<HTMLDivElement>(null);
  const callback = useRef(onResult);
  const passwordRef = useRef(password);
  const [retry, setRetry] = useState(0);
  const [ready, setReady] = useState<number>();
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const canPrepare = Boolean(config.data?.enabled && (action === "signin" || password));
  useEffect(() => { callback.current = onResult; passwordRef.current = password; }, [onResult, password]);

  useEffect(() => {
    if (!canPrepare) return;
    const controller = new AbortController();
    const element = target.current;
    if (!element) return;
    const current = element;
    async function showButton() {
      try {
        const [sdk, { data: challenge }] = await Promise.all([
          loadGoogle(),
          apiClient.post<{ client_id: string; nonce: string }>("/api/auth/google/challenge", { action }, { signal: controller.signal }),
        ]);
        if (controller.signal.aborted) return;
        sdk.initialize({ client_id: challenge.client_id, nonce: challenge.nonce, callback: async ({ credential }) => {
          if (controller.signal.aborted) return;
          setPending(true);
          try {
            const { data } = await apiClient.post<AuthResult>("/api/auth/google", {
              action, nonce: challenge.nonce, credential,
              password: action === "link" ? passwordRef.current : undefined,
            }, { signal: controller.signal });
            if (!controller.signal.aborted) await callback.current(data);
          } catch (cause) {
            if (!controller.signal.aborted) setError(profileError(cause));
          } finally {
            if (!controller.signal.aborted) setPending(false);
          }
        } });
        sdk.renderButton(current, { theme: "outline", size: "large", text: "continue_with", width: Math.min(340, current.parentElement?.clientWidth || 240) });
        setReady(retry);
      } catch (cause) {
        if (!controller.signal.aborted) setError(cause instanceof Error && !("response" in cause) ? cause.message : profileError(cause));
      }
    }
    void showButton();
    return () => { controller.abort(); current.replaceChildren(); };
  }, [action, canPrepare, retry]);

  const hidden = !canPrepare || ready !== retry || Boolean(error);
  return <div className="google-signin">
    {canPrepare ? <div className="google-signin__button" ref={target} style={hidden ? { position: "absolute", visibility: "hidden" } : undefined} /> : null}
    {hidden ? <button className="button-secondary" type="button" disabled={!error} onClick={() => { setError(""); setRetry(value => value + 1); }}>
      {error ? "Try Google again" : action === "link" ? "Connect Google" : "Continue with Google"}
    </button> : null}
    {config.isError ? <p role="status">Google sign-in status is unavailable. <button type="button" onClick={() => void config.refetch()}>Retry</button></p> : null}
    {config.data?.enabled === false ? <p>Google sign-in is awaiting setup on this server.</p> : null}
    {pending ? <p role="status">Signing in with Google…</p> : null}
    {error ? <p role="alert">{error}</p> : null}
  </div>;
}
