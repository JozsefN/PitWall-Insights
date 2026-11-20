import { NavLink } from "react-router-dom";
import { navigationItems } from "./navigation";
import { useAuthSession } from "../../features/auth/useAuthSession";

export function AppSidebar() {
  const { data } = useAuthSession();
  return (
    <aside className="app-sidebar">
      <div className="app-sidebar__inner">
        {(["Explore", "Workspace", "System"] as const).filter(section => section !== "System" || data?.role === "admin").map((section) => (
          <section key={section} className="app-sidebar__section">
            <h2>{section === "System" ? "Admin" : section}</h2>
            <nav aria-label={`${section === "System" ? "Admin" : section} navigation`}>
              {navigationItems
                .filter((item) => item.section === section)
                .map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === "/"}
                    className={({ isActive }) =>
                      `app-sidebar__link${isActive ? " is-active" : ""}`
                    }
                  >
                    <span>{item.label}</span>
                    <small>{item.note}</small>
                  </NavLink>
                ))}
            </nav>
          </section>
        ))}
      </div>
    </aside>
  );
}
