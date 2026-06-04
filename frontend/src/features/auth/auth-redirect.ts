type RedirectLocation = {
  pathname: string;
  search?: string;
  hash?: string;
};

export type AuthRedirectState = {
  from: RedirectLocation;
};

export function buildAuthRedirectState(location: RedirectLocation): AuthRedirectState {
  return {
    from: {
      pathname: location.pathname,
      search: location.search,
      hash: location.hash,
    },
  };
}

export function getAuthRedirectPath(state: unknown, fallback = "/"): string {
  if (!state || typeof state !== "object" || !("from" in state)) {
    return fallback;
  }

  const from = (state as { from?: unknown }).from;

  if (!from || typeof from !== "object") {
    return fallback;
  }

  const location = from as Partial<RedirectLocation>;
  const pathname = location.pathname;

  if (
    typeof pathname !== "string" ||
    !pathname.startsWith("/") ||
    pathname.startsWith("//") ||
    pathname === "/login" ||
    pathname === "/signup"
  ) {
    return fallback;
  }

  const search =
    typeof location.search === "string" && location.search.startsWith("?")
      ? location.search
      : "";
  const hash =
    typeof location.hash === "string" && location.hash.startsWith("#")
      ? location.hash
      : "";

  return `${pathname}${search}${hash}`;
}
