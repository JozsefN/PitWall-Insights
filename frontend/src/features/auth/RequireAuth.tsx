import type { PropsWithChildren } from "react";
import { Link, useLocation } from "react-router-dom";
import { PageContainer } from "../../app/layout/PageContanier";
import { buildAuthRedirectState } from "./auth-redirect";
import { useAuthSession } from "./useAuthSession";

type RequireAuthProps = PropsWithChildren<{
  title?: string;
  description?: string;
}>;

export function RequireAuth({
  children,
  title = "Session Explorer",
  description = "Sign in to open the session archive, prepare lookback workspaces, run replay mode, and keep your motorsport analysis tied to your account.",
}: RequireAuthProps) {
  const location = useLocation();
  const authSession = useAuthSession();
  const redirectState = buildAuthRedirectState(location);

  if (authSession.data?.authenticated) {
    return <>{children}</>;
  }

  if (authSession.isLoading) {
    return (
      <PageContainer>
        <section className="surface-card p-6 sm:p-8">
          <span className="ui-pill ui-pill--focus">Member access</span>
          <p className="mt-5 text-sm leading-7 text-[var(--color-text-secondary)]">
            Checking your session before opening the workspace...
          </p>
        </section>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <section className="surface-card overflow-hidden p-6 sm:p-8 lg:p-10">
        <div className="flex flex-col gap-8 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <span className="ui-pill ui-pill--ready">Member feature</span>
            <h1 className="display-font mt-5 text-[2.2rem] leading-none text-white sm:text-[2.8rem]">
              {title}
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-[var(--color-text-secondary)] sm:text-base">
              {description}
            </p>
          </div>

          <span className="rounded-full border border-[var(--color-border-subtle)] bg-white/[0.02] px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--color-text-muted)]">
            Login required
          </span>
        </div>

        <div className="mt-8 grid gap-5 border-t border-[var(--color-border-subtle)] pt-6 md:grid-cols-3">
          <div className="min-w-0">
            <span className="ui-pill ui-pill--focus">Lookback</span>
            <h2 className="mt-4 text-lg font-semibold text-white">Telemetry workspaces</h2>
            <p className="mt-3 text-sm leading-7 text-[var(--color-text-secondary)]">
              Compare drivers, laps, and session context after signing in.
            </p>
          </div>

          <div className="min-w-0">
            <span className="ui-pill ui-pill--live">Replay</span>
            <h2 className="mt-4 text-lg font-semibold text-white">Simulation controls</h2>
            <p className="mt-3 text-sm leading-7 text-[var(--color-text-secondary)]">
              Open replay mode with driver selection and session timing controls.
            </p>
          </div>

          <div className="min-w-0">
            <span className="ui-pill ui-pill--ready">Account</span>
            <h2 className="mt-4 text-lg font-semibold text-white">Saved access</h2>
            <p className="mt-3 text-sm leading-7 text-[var(--color-text-secondary)]">
              Keep authenticated-only workspace features behind member access.
            </p>
          </div>
        </div>

        <div className="mt-8 flex flex-wrap gap-3">
          <Link to="/signup" state={redirectState} className="button-primary">
            Sign up
          </Link>
          <Link to="/login" state={redirectState} className="button-secondary">
            Sign in
          </Link>
        </div>
      </section>
    </PageContainer>
  );
}
