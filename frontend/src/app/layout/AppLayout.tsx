import { Outlet, useLocation } from "react-router-dom";
import { AppHeader } from "./AppHeader";
import { AppSidebar } from "./AppSidebar";

export function AppLayout() {
  const { pathname } = useLocation();
  const isMarketingSurface =
    pathname === "/" || pathname === "/login" || pathname === "/signup";

  return (
    <div className="min-h-screen bg-[var(--color-bg-primary)] text-white">
      <AppHeader />

      <div
        className={[
          "min-h-[calc(100vh-72px)]",
          isMarketingSurface ? "" : "mx-auto flex w-full max-w-[1440px]",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        {isMarketingSurface ? null : <AppSidebar />}

        <main className="min-w-0 flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
