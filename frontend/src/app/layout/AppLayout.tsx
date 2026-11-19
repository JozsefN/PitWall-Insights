import { Outlet, useLocation } from "react-router-dom";
import { AppHeader } from "./AppHeader";
import { AppSidebar } from "./AppSidebar";
import "./app-layout.css";

export function AppLayout() {
  const { pathname } = useLocation();
  const isMarketingSurface =
    pathname === "/" || pathname === "/login" || pathname === "/signup";

  return (
    <div className="min-h-screen bg-[var(--color-bg-primary)] text-[var(--color-text-primary)]">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <AppHeader />

      <div
        className={[
          "min-h-[calc(100vh-72px)]",
          isMarketingSurface ? "" : "mx-auto flex w-full max-w-[1680px]",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        {isMarketingSurface ? null : <AppSidebar />}

        <main id="main-content" tabIndex={-1} className="min-w-0 flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
