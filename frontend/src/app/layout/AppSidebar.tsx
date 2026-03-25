import { NavLink } from "react-router-dom";

type NavItem = {
  label: string;
  to: string;
};

const navItems: NavItem[] = [
  { label: "Home", to: "/" },
  { label: "Sessions", to: "/sessions" },
  { label: "Live", to: "/live/demo" },
  { label: "Compare", to: "/compare/demo" },
  { label: "Login", to: "/login" },
  { label: "Signup", to: "/signup" },
];

function linkClassName(isActive: boolean) {
  return [
    "block rounded-lg px-3 py-2 text-sm transition",
    isActive
      ? "bg-neutral-800 text-white"
      : "text-neutral-400 hover:bg-neutral-900 hover:text-white",
  ].join(" ");
}

export function AppSidebar() {
  return (
    <aside className="hidden w-64 shrink-0 border-r border-neutral-800 bg-neutral-950 lg:block">
      <div className="p-4">
        <div className="mb-4 px-3 text-xs font-medium uppercase tracking-[0.2em] text-neutral-500">
          Navigation
        </div>

        <nav className="space-y-1">
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} className={({ isActive }) => linkClassName(isActive)}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </aside>
  );
}