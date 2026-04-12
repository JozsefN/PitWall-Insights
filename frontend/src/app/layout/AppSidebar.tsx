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
        badge: "Ready",
        tone: "ready",
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
    "block rounded-[18px] border px-3 py-3 transition duration-200 group-hover:px-4 group-focus-within:px-4",
    isActive
      ? "border-[var(--color-border-strong)] bg-white/[0.03] text-white"
      : "border-transparent bg-transparent text-[var(--color-text-secondary)] hover:border-[var(--color-border-subtle)] hover:bg-white/[0.02] hover:text-white",
  ].join(" ");
}

function compactStatusDotClass(tone: NavItem["tone"]) {
  switch (tone) {
    case "ready":
      return "bg-emerald-400";
    case "soon":
      return "bg-amber-400";
    case "focus":
      return "bg-sky-400";
    case "live":
      return "bg-red-500";
    case "improved":
      return "bg-green-400";
    default:
      return "bg-white";
  }
}

export function AppSidebar() {
  return (
    <aside className="group hidden shrink-0 border-r border-[var(--color-border-subtle)] transition-[width] duration-300 ease-out lg:block lg:w-[152px] lg:hover:w-[288px] lg:focus-within:w-[288px]">
      <div className="sticky top-[88px] p-3 transition-[padding] duration-300 group-hover:p-4 group-focus-within:p-4">
        {navSections.map((section) => (
          <section key={section.label} className="mb-6">
            <div className="mb-3 overflow-hidden px-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-[var(--color-text-muted)] transition-[max-height,opacity] duration-200 lg:max-h-0 lg:opacity-0 lg:group-hover:max-h-10 lg:group-hover:opacity-100 lg:group-focus-within:max-h-10 lg:group-focus-within:opacity-100">
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
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-semibold leading-5 text-inherit">
                        {item.label}
                      </div>
                      <div className="mt-1 max-h-0 overflow-hidden text-xs leading-5 text-[var(--color-text-muted)] opacity-0 transition-[max-height,opacity] duration-200 delay-75 group-hover:max-h-24 group-hover:opacity-100 group-focus-within:max-h-24 group-focus-within:opacity-100">
                        {item.note}
                      </div>
                    </div>

                    <div className="flex shrink-0 items-center">
                      <span
                        className={`h-2.5 w-2.5 rounded-full transition-opacity duration-150 group-hover:opacity-0 group-focus-within:opacity-0 ${compactStatusDotClass(item.tone)}`}
                      />
                      <span className="max-w-0 overflow-hidden opacity-0 transition-[max-width,opacity,margin,transform] duration-200 delay-150 group-hover:ml-2 group-hover:max-w-[96px] group-hover:translate-x-0 group-hover:opacity-100 group-focus-within:ml-2 group-focus-within:max-w-[96px] group-focus-within:translate-x-0 group-focus-within:opacity-100">
                        <span className={`ui-pill ui-pill--${item.tone} whitespace-nowrap`}>
                          {item.badge}
                        </span>
                      </span>
                    </div>
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
