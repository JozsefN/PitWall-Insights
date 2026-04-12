export type HealthStatus = "healthy" | "degraded" | "down" | "unknown";

export type HealthItem = {
  key: string;
  label: string;
  status: HealthStatus;
};

export type HealthOverviewModel = {
  items: HealthItem[];
};

export function normalizeHealthStatus(value: unknown): HealthStatus {
  if (!value) return "unknown";

  if (typeof value === "string") {
    const v = value.toLowerCase();

    if (
      v.startsWith("ready") ||
      v.startsWith("connected") ||
      v.startsWith("healthy")
    ) {
      return "healthy";
    }

    if (v.startsWith("error") || v.startsWith("failed") || v.startsWith("disconnected")) {
      return "down";
    }

    if (v.startsWith("stub") || v.startsWith("not_implemented")) {
      return "degraded";
    }

    if (["ok", "healthy", "up", "connected", "ready", "enabled"].includes(v)) {
      return "healthy";
    }

    if (["degraded", "warning", "stub", "not_implemented", "pending"].includes(v)) {
      return "degraded";
    }

    if (["down", "error", "failed", "disconnected"].includes(v)) {
      return "down";
    }
  }

  if (typeof value === "object" && value !== null) {
    if ("status" in value) {
      return normalizeHealthStatus((value as { status?: unknown }).status);
    }
  }

  return "unknown";
}

export function mapHealthOverview(params: {
  api?: unknown;
  auth?: unknown;
  ingestion?: unknown;
  normalization?: unknown;
}): HealthOverviewModel {
  return {
    items: [
      {
        key: "api",
        label: "API",
        status: normalizeHealthStatus(params.api),
      },
      {
        key: "auth",
        label: "Auth",
        status: normalizeHealthStatus(params.auth),
      },
      {
        key: "ingestion",
        label: "Ingestion",
        status: normalizeHealthStatus(params.ingestion),
      },
      {
        key: "normalization",
        label: "Normalization",
        status: normalizeHealthStatus(params.normalization),
      },
    ],
  };
}
