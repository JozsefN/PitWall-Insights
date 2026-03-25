import type { RouteObject } from "react-router-dom";
import { Navigate } from "react-router-dom";
import { AppLayout } from "../layout/AppLayout";

import { HomePage } from "../../pages/HomePage";
import { SystemHealthPage } from "../../pages/SystemHealthPage"

// Temporary page placeholders.
// Replace these imports with real page files as you create them.
function SessionsPage() {
  return <div className="p-6 text-neutral-200">Sessions page placeholder</div>;
}

function SessionDetailPage() {
  return <div className="p-6 text-neutral-200">Session detail placeholder</div>;
}

function LiveRacePage() {
  return <div className="p-6 text-neutral-200">Live race placeholder</div>;
}

function ComparePage() {
  return <div className="p-6 text-neutral-200">Compare page placeholder</div>;
}

function LoginPage() {
  return <div className="p-6 text-neutral-200">Login page placeholder</div>;
}

function SignupPage() {
  return <div className="p-6 text-neutral-200">Signup page placeholder</div>;
}

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "sessions", element: <SessionsPage /> },
      { path: "sessions/:sessionId", element: <SessionDetailPage /> },
      { path: "live/:sessionId", element: <LiveRacePage /> },
      { path: "compare/:sessionId", element: <ComparePage /> },
      { path: "login", element: <LoginPage /> },
      { path: "signup", element: <SignupPage /> },
      { path: "home", element: <Navigate to="/" replace /> },

       { path: "system/health", element: <SystemHealthPage /> },
    ],
  },
];