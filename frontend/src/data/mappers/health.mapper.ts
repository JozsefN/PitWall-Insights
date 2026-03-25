export type HealthStatus = "healthy" | "degraded" | "down" | "unknown";

export type HealthItem = {
  key: string;
  label: string;
  status: HealthStatus;
};

export type HealthOverviewModel = {
  items: HealthItem[];
};

function normalizeStatus(value: unknown): HealthStatus {
  if (!value) return "unknown";

  if (typeof value === "string") {
    const v = value.toLowerCase();

    if (["ok", "healthy", "up"].includes(v)) return "healthy";
    if (["degraded", "warning"].includes(v)) return "degraded";
    if (["down", "error", "failed"].includes(v)) return "down";
  }

  if (typeof value === "object" && value !== null) {
    if ("status" in value) {
      return normalizeStatus((value as any).status);
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
        status: normalizeStatus(params.api),
      },
      {
        key: "auth",
        label: "Auth",
        status: normalizeStatus(params.auth),
      },
      {
        key: "ingestion",
        label: "Ingestion",
        status: normalizeStatus(params.ingestion),
      },
      {
        key: "normalization",
        label: "Normalization",
        status: normalizeStatus(params.normalization),
      },
    ],
  };
}