import { Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { logout } from "../../data/api/auth.api";
import { useAuthSession } from "../../features/auth/useAuthSession";

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
    <header className="sticky top-0 z-30 border-b border-neutral-800 bg-neutral-950/90 backdrop-blur">
      <div className="flex h-14 items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link to="/" className="text-sm font-semibold tracking-wide text-white">
          PITWALL INSIGHTS
        </Link>

        <div className="flex items-center gap-3 text-sm">
          <span className="rounded-md border border-neutral-800 px-2 py-1 text-neutral-400">
            Telemetry
          </span>
          <span className="rounded-md border border-neutral-800 px-2 py-1 text-neutral-400">
            Race Viewer
          </span>

          {isLoading ? null : data?.authenticated ? (
            <>
              <span className="text-neutral-300">{data.email}</span>
              <button
                onClick={handleLogout}
                className="rounded-md border border-neutral-800 px-3 py-1 text-neutral-300 hover:text-white"
              >
                Logout
              </button>
            </>
          ) : (
            <>
              <Link
                to="/login"
                className="rounded-md border border-neutral-800 px-3 py-1 text-neutral-300 hover:text-white"
              >
                Login
              </Link>
              <Link
                to="/signup"
                className="rounded-md bg-white px-3 py-1 text-black hover:bg-neutral-200"
              >
                Sign up
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}