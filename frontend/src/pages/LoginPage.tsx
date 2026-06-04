import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { login } from "../data/api/auth.api";
import { getAuthRedirectPath } from "../features/auth/auth-redirect";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const redirectTo = getAuthRedirectPath(location.state);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: async (data) => {
      localStorage.setItem("auth_token", data.access_token);

      queryClient.setQueryData(["auth-session"], {
        authenticated: true,
        user_id: null,
        email,
      });

      await queryClient.invalidateQueries({ queryKey: ["auth-session"] });
      navigate(redirectTo, { replace: true });
    },
  });

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    mutation.mutate({ email, password });
  }

  const errorMessage =
    mutation.error instanceof Error
      ? mutation.error.message
      : "Login failed";

  return (
    <div className="mx-auto flex min-h-[calc(100vh-72px)] max-w-md items-center px-4 py-10">
      <div className="surface-card w-full p-8">
        <span className="ui-pill ui-pill--focus">Member access</span>
        <h1 className="display-font mt-5 text-[2rem] leading-none text-white">Welcome back</h1>
        <p className="mt-3 text-sm leading-7 text-[var(--color-text-secondary)]">
          Sign in to continue into Pitwall Insights.
        </p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
          <div>
            <label htmlFor="login-email" className="mb-2 block text-sm text-white/90">
              Email
            </label>
            <input
              id="login-email"
              type="email"
              className="w-full rounded-2xl border border-[var(--color-border-subtle)] bg-[var(--color-bg-secondary)] px-4 py-3 text-white outline-none transition focus:border-[var(--color-accent-blue)] focus:ring-2 focus:ring-[rgba(30,144,255,0.18)]"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              autoComplete="email"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label htmlFor="login-password" className="mb-2 block text-sm text-white/90">
              Password
            </label>
            <input
              id="login-password"
              type="password"
              className="w-full rounded-2xl border border-[var(--color-border-subtle)] bg-[var(--color-bg-secondary)] px-4 py-3 text-white outline-none transition focus:border-[var(--color-accent-blue)] focus:ring-2 focus:ring-[rgba(30,144,255,0.18)]"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              autoComplete="current-password"
              placeholder="Your password"
            />
          </div>

          {mutation.isError ? (
            <div className="rounded-2xl border border-[rgba(220,38,38,0.38)] bg-[rgba(220,38,38,0.12)] px-4 py-3 text-sm text-red-200">
              {errorMessage}
            </div>
          ) : null}

          <button
            type="submit"
            className="button-primary w-full"
            disabled={mutation.isPending}
          >
            {mutation.isPending ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="mt-5 text-sm text-[var(--color-text-secondary)]">
          Need an account?{" "}
          <Link to="/signup" state={location.state} className="text-white underline underline-offset-4">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}
