import { Link, NavLink, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { logout } from "../../data/api/auth.api";
import { useAuthSession } from "../../features/auth/useAuthSession";
import { ThemeToggle } from "../../features/theme/ThemeToggle";

import { navigationItems } from "./navigation";

export function AppHeader() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data, isLoading } = useAuthSession();

  async function handleLogout() {
    logout();
    queryClient.removeQueries({ queryKey: ["profile"] });

    await queryClient.setQueryData(["auth-session"], {
      authenticated: false,
      user_id: null,
      email: null,
    });

    await queryClient.invalidateQueries({ queryKey: ["auth-session"] });

    navigate("/login");
  }

  return (
    <header className="app-header">
      <div className="app-header__inner">
        <Link to="/" className="app-header__brand">
          <span className="app-header__mark" aria-hidden="true" />
          <span>
            <strong>Pitwall Insights</strong>
            <small>Motorsport intelligence</small>
          </span>
        </Link>
        <nav className="app-header__nav" aria-label="Main navigation">
          {navigationItems
            .filter((item) => item.section !== "System")
            .map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `app-header__link${isActive ? " is-active" : ""}`
                }
              >
                {item.label}
              </NavLink>
            ))}
        </nav>
        <div className="app-header__account">
          <ThemeToggle />
          {isLoading ? (
            <span>Checking session...</span>
          ) : data?.authenticated ? (
            <>
              <Link to="/profile"
                className="app-header__profile"
                aria-label="Open profile"
                title={data.email ?? undefined}
              >
                <span className="app-header__identity">{data.email}</span><span className="app-header__profile-label">Profile</span>
              </Link>
              <Link
                to="/system/health"
                className="button-secondary app-header__diagnostics"
              >
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
    </header>
  );
}
