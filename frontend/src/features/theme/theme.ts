export type Theme = "dark" | "light";

const key = "pitwall-theme";

export function initialTheme(): Theme {
  try {
    const stored = localStorage.getItem(key);
    if (stored === "dark" || stored === "light") return stored;
  } catch {
    // The theme still works when a browser blocks storage.
  }
  return matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function applyTheme(theme: Theme, persist = false) {
  document.documentElement.dataset.theme = theme;
  if (!persist) return;
  try {
    localStorage.setItem(key, theme);
  } catch {
    // Keep the choice for the current page.
  }
}
