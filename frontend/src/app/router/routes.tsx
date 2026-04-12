import type { RouteObject } from "react-router-dom";
import { Navigate } from "react-router-dom";
import { AppLayout } from "../layout/AppLayout";

import { HomePage } from "../../pages/HomePage";
import { SystemHealthPage } from "../../pages/SystemHealthPage";
import { LoginPage } from "../../pages/LoginPage";
import { SignupPage } from "../../pages/SignupPage";
import { FeaturePlaceholderPage } from "../../pages/FeaturePlaceholderPage";
import { SessionsExplorerPage } from "../../pages/SessionsExplorerPage";
import { SessionWorkspacePage } from "../../pages/SessionWorkspacePage";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <HomePage /> },
      {
        path: "sessions",
        element: <SessionsExplorerPage />,
      },
      {
        path: "sessions/:sessionId",
        element: <SessionWorkspacePage />,
      },
      {
        path: "live",
        element: (
          <FeaturePlaceholderPage
            eyebrow="Live race"
            title="Live Race Command"
            description="The live race surface should become the quickest way to follow timing, gaps, tyre windows, and high-priority moments during a session."
            tone="live"
            details={[
              {
                title: "Timing tower",
                body: "Positions, intervals, lap progression, and live movement should stay visible without feeling crowded.",
              },
              {
                title: "Tyre and stint view",
                body: "Compound windows and strategy context belong here so the race can be read beyond raw positions.",
              },
              {
                title: "Race control context",
                body: "Incidents, cautions, and important shifts in the race should slot into the same command surface.",
              },
            ]}
          />
        ),
      },
      {
        path: "live/:sessionId",
        element: (
          <FeaturePlaceholderPage
            eyebrow="Live race"
            title="Live Race Detail"
            description="This route will host a session-specific live view once the race workspace is wired to real event context."
            tone="live"
            details={[
              {
                title: "Pinned live session",
                body: "Opening a specific session should preserve the same live race logic while focusing on one event.",
              },
              {
                title: "Race-first layout",
                body: "Timing, strategy, and key context will stay prioritized over secondary information.",
              },
              {
                title: "Fast return path",
                body: "The larger home hub and related surfaces should remain one step away while following the live session.",
              },
            ]}
          />
        ),
      },
      {
        path: "story-feed",
        element: (
          <FeaturePlaceholderPage
            eyebrow="Story feed"
            title="Story Feed"
            description="A news wall for official F1 videos, weekend headlines, and the ongoing stories around the paddock."
            tone="improved"
            details={[
              {
                title: "Official video wall",
                body: "F1 YouTube videos and related clips should feel native to the product instead of floating in a disconnected list.",
              },
              {
                title: "Headline stack",
                body: "Breaking stories, weekend notes, and follow-up news should be readable in the same feed as the videos.",
              },
              {
                title: "Race-week rhythm",
                body: "Between sessions, this should become the fastest way to catch up on what changed and why it matters.",
              },
            ]}
          />
        ),
      },
      {
        path: "standings",
        element: (
          <FeaturePlaceholderPage
            eyebrow="Standings"
            title="Season Standings"
            description="Drivers and constructors tables should stay close at hand, especially when the front page falls back from live mode."
            tone="focus"
            details={[
              {
                title: "Drivers table",
                body: "Keep the championship order, points gaps, and recent movement clear without making the table feel dense.",
              },
              {
                title: "Constructors view",
                body: "Teams need the same level of clarity, with enough context to read momentum across the season.",
              },
              {
                title: "Season context",
                body: "This surface should connect standings changes back to recent race weekends and storylines.",
              },
            ]}
          />
        ),
      },
      { path: "compare/:sessionId", element: <Navigate to="/standings" replace /> },
      { path: "login", element: <LoginPage /> },
      { path: "signup", element: <SignupPage /> },
      { path: "home", element: <Navigate to="/" replace /> },
      { path: "system/health", element: <SystemHealthPage /> },
    ],
  },
];
