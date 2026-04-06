import type { RouteObject } from "react-router-dom";
import { Navigate } from "react-router-dom";
import { AppLayout } from "../layout/AppLayout";

import { HomePage } from "../../pages/HomePage";
import { SystemHealthPage } from "../../pages/SystemHealthPage";
import { LoginPage } from "../../pages/LoginPage";
import { SignupPage } from "../../pages/SignupPage";

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