export function tokenExpiresSoon(token: string, nowMs = Date.now()): boolean {
  try {
    const payload = JSON.parse(
      atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")),
    );
    return (
      typeof payload.exp === "number" && payload.exp * 1000 - nowMs < 5 * 60_000
    );
  } catch {
    return false;
  }
}

export const AUTH_EXPIRED_EVENT = "pitwall:auth-expired";
