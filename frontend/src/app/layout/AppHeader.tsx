import { Link, NavLink, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { logout } from "../../data/api/auth.api";
import { useAuthSession } from "../../features/auth/useAuthSession";

const headerLinks = [
  { label: "Home", to: "/", end: true },
  { label: "Live Race", to: "/live", end: false },
  { label: "Story Feed", to: "/story-feed", end: false },
  { label: "Sessions", to: "/sessions", end: false },
  { label: "Standings", to: "/standings", end: false },
];

function headerLinkClassName(isActive: boolean) {
  return [
    "inline-flex min-h-[38px] items-center rounded-full border px-4 text-[13px] font-medium transition duration-150",
    isActive
      ? "border-[var(--color-border-strong)] bg-[rgba(30,144,255,0.14)] text-white"
      : "border-transparent text-[var(--color-text-secondary)] hover:border-[var(--color-border-subtle)] hover:bg-white/[0.03] hover:text-white",
  ].join(" ");
}

export function AppHeader() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data, isLoading } = useAuthSession();

  async function handleLogout() {
    logout();

    await queryClient.setQueryData(["auth-session"], {
      authenticated: false,
      user_id: null,
      email: null,
    });

    await queryClient.invalidateQueries({ queryKey: ["auth-session"] });

    navigate("/login");
  }

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--color-border-subtle)] bg-[rgba(11,13,18,0.88)] backdrop-blur-xl">
      <div className="mx-auto flex max-w-[1680px] flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
        <div className="flex items-center justify-between gap-4">
          <Link to="/" className="group flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-[rgba(225,6,0,0.24)] bg-[rgba(225,6,0,0.1)] shadow-[0_0_24px_rgba(225,6,0,0.18)]">
              <span className="h-3 w-3 rounded-full bg-[var(--color-accent-red)] shadow-[0_0_18px_rgba(225,6,0,0.55)]" />
            </span>

            <span className="flex flex-col">
              <span className="display-font text-sm text-white sm:text-base">
                Pitwall Insights
              </span>
              <span className="text-[11px] uppercase tracking-[0.22em] text-[var(--color-text-muted)]">
                Motorsport intelligence interface
              </span>
            </span>
          </Link>
        </div>

        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-end">
          <nav className="flex flex-wrap items-center gap-2">
            {headerLinks.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) => headerLinkClassName(isActive)}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="flex flex-wrap items-center gap-3 text-sm">
            {isLoading ? (
              <span className="rounded-full border border-[var(--color-border-subtle)] bg-white/[0.02] px-4 py-2 text-[13px] text-[var(--color-text-secondary)]">
                Checking session...
              </span>
            ) : data?.authenticated ? (
              <>
                <span className="rounded-full border border-[var(--color-border-subtle)] bg-white/[0.02] px-4 py-2 text-[13px] text-[var(--color-text-secondary)]">
                  {data.email}
                </span>
                <Link to="/system/health" className="button-secondary">
                  Diagnostics
                </Link>
                <button onClick={handleLogout} className="button-secondary">
                  Sign out
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="button-secondary">
                  Sign in
                </Link>
                <Link to="/signup" className="button-primary">
                  Sign up
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
