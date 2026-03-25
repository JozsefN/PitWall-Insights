import { Link } from "react-router-dom";

export function AppHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-neutral-800 bg-neutral-950/90 backdrop-blur">
      <div className="flex h-14 items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link to="/" className="text-sm font-semibold tracking-wide text-white">
          PITWALL INSIGHTS
        </Link>

        <div className="flex items-center gap-3 text-sm text-neutral-400">
          <span className="rounded-md border border-neutral-800 px-2 py-1">Telemetry</span>
          <span className="rounded-md border border-neutral-800 px-2 py-1">Race Viewer</span>
        </div>
      </div>
    </header>
  );
}