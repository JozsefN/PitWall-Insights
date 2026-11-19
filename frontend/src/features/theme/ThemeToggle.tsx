import { useState } from "react";
import { applyTheme, initialTheme, type Theme } from "./theme";

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const next = theme === "dark" ? "light" : "dark";

  return (
    <button
      type="button"
      className="button-secondary app-theme-toggle"
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      onClick={() => {
        applyTheme(next, true);
        setTheme(next);
      }}
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
        {next === "dark" ? <path d="M20.9 13A9 9 0 0 1 11 3.1 9 9 0 1 0 20.9 13Z" /> : <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.4 1.4m11.2 11.2L19 19M5 19l1.4-1.4M17.6 6.4 19 5" /></>}
      </svg>
      <span>{next === "light" ? "Light" : "Dark"}</span>
    </button>
  );
}
