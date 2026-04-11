import { NavLink } from "react-router-dom";

type NavItem = {
  label: string;
  to: string;
  note: string;
  badge: string;
  tone: "ready" | "soon" | "focus" | "live" | "improved";
};

type NavSection = {
  label: string;
  items: NavItem[];
};

const navSections: NavSection[] = [
  {
    label: "Explore",
    items: [
      {
        label: "Home",
        to: "/",
        note: "Jump back to the race hub and primary feature surfaces",
        badge: "Ready",
        tone: "ready",
      },
      {
        label: "Live Race",
        to: "/live",
        note: "Timing, gaps, tyres, and race context",
        badge: "Preview",
        tone: "live",
      },
      {
        label: "Story Feed",
        to: "/story-feed",
        note: "News wall for F1 videos, headlines, and weekend stories",
        badge: "Preview",
        tone: "improved",
      },
      {
        label: "Sessions",
        to: "/sessions",
        note: "Previous races, qualifying, and weekend lookbacks",
        badge: "Preview",
        tone: "soon",
      },
      {
        label: "Standings",
        to: "/standings",
        note: "Drivers and constructors tables in one season view",
        badge: "Preview",
        tone: "focus",
      },
    ],
  },
  {
    label: "System",
    items: [
      {
        label: "System Health",
        to: "/system/health",
        note: "Backend and module diagnostics",
        badge: "Live",
        tone: "ready",
      },
    ],
  },
];

function linkClassName(isActive: boolean) {
  return [
    "block rounded-[18px] border px-4 py-4 transition duration-150",
    isActive
      ? "border-[var(--color-border-strong)] bg-white/[0.03] text-white"
      : "border-transparent bg-transparent text-[var(--color-text-secondary)] hover:border-[var(--color-border-subtle)] hover:bg-white/[0.02] hover:text-white",
  ].join(" ");
}

export function AppSidebar() {
  return (
    <aside className="hidden w-[280px] shrink-0 border-r border-[var(--color-border-subtle)] lg:block">
      <div className="sticky top-[88px] p-4">
        {navSections.map((section) => (
          <section key={section.label} className="mb-6">
            <div className="mb-3 px-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-[var(--color-text-muted)]">
              {section.label}
            </div>

            <nav className="space-y-2">
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) => linkClassName(isActive)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-inherit">{item.label}</div>
                      <div className="mt-1 text-xs leading-5 text-[var(--color-text-muted)]">
                        {item.note}
                      </div>
                    </div>

                    <span className={`ui-pill ui-pill--${item.tone}`}>
                      {item.badge}
                    </span>
                  </div>
                </NavLink>
              ))}
            </nav>
          </section>
        ))}
      </div>
    </aside>
  );
}
