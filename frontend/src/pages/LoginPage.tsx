import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { login } from "../data/api/auth.api";

export function LoginPage() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: (data) => {
      localStorage.setItem("auth_token", data.access_token);
      navigate("/");
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
    <div className="mx-auto flex min-h-[calc(100vh-56px)] max-w-md items-center px-4 py-8">
      <div className="w-full rounded-2xl border border-neutral-800 bg-neutral-900 p-6 shadow-sm">
        <h1 className="mb-2 text-2xl font-semibold text-white">Welcome back</h1>
        <p className="mb-6 text-sm text-neutral-400">
          Log in to continue to Pitwall Insights.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="login-email" className="mb-1 block text-sm text-neutral-300">
              Email
            </label>
            <input
              id="login-email"
              type="email"
              className="w-full rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2 text-white outline-none transition focus:border-neutral-500"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              autoComplete="email"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label htmlFor="login-password" className="mb-1 block text-sm text-neutral-300">
              Password
            </label>
            <input
              id="login-password"
              type="password"
              className="w-full rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2 text-white outline-none transition focus:border-neutral-500"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              autoComplete="current-password"
              placeholder="Your password"
            />
          </div>

          {mutation.isError ? (
            <div className="rounded-lg border border-red-900 bg-red-950/40 px-3 py-2 text-sm text-red-300">
              {errorMessage}
            </div>
          ) : null}

          <button
            type="submit"
            className="w-full rounded-lg bg-white px-4 py-2 font-medium text-black transition hover:bg-neutral-200 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={mutation.isPending}
          >
            {mutation.isPending ? "Logging in..." : "Login"}
          </button>
        </form>

        <p className="mt-4 text-sm text-neutral-400">
          Need an account?{" "}
          <Link to="/signup" className="text-white underline underline-offset-4">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}