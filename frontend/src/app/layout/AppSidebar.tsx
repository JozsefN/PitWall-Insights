import { NavLink } from "react-router-dom";
import { navigationItems } from "./navigation";

export function AppSidebar() {
  return (
    <aside className="app-sidebar">
      <div className="app-sidebar__inner">
        {(["Explore", "Workspace", "System"] as const).map((section) => (
          <section key={section} className="app-sidebar__section">
            <h2>{section}</h2>
            <nav aria-label={`${section} navigation`}>
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
        <div className="app-sidebar__footer">
          <span aria-hidden="true" />
          Built around your race.
        </div>
      </div>
    </aside>
  );
}
