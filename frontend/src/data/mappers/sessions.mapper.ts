export type SessionsSummaryModel = {
  total: number;
  active: number;
  failed: number;
};

type SessionRecord = {
  id?: string;
  status?: string;
  state?: string;
  health?: string;
};

function normalizeSessions(data: unknown): SessionRecord[] {
  if (Array.isArray(data)) {
    return data as SessionRecord[];
  }

  if (
    typeof data === "object" &&
    data !== null &&
    "items" in data &&
    Array.isArray((data as any).items)
  ) {
    return (data as any).items;
  }

  return [];
}

function getStatus(session: SessionRecord): string {
  return String(
    session.status ??
      session.state ??
      session.health ??
      ""
  ).toLowerCase();
}

export function mapSessionsSummary(data: unknown): SessionsSummaryModel {
  const sessions = normalizeSessions(data);

  const total = sessions.length;

  const active = sessions.filter((s) => {
    const status = getStatus(s);
    return ["active", "running", "in_progress"].includes(status);
  }).length;

  const failed = sessions.filter((s) => {
    const status = getStatus(s);
    return ["failed", "error"].includes(status);
  }).length;

  return {
    total,
    active,
    failed,
  };
}