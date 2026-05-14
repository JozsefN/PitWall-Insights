import { apiClient } from "./client";
import type {
  CarTelemetrySampleDto,
  EntryLapDto,
  PositionSampleDto,
  SessionCatalogItemDto,
  SessionCircuitCornerDto,
  SessionDto,
  SessionEntryDto,
  SessionImportRequestDto,
  SessionTelemetryQuery,
  SessionTickDto,
  SessionTrackStatusEventDto,
} from "../contracts/sessions.contracts";

export async function listSessions(): Promise<SessionDto[]> {
  const { data } = await apiClient.get("/api/sessions");
  return data;
}

export async function listSessionCatalog(season?: number): Promise<SessionCatalogItemDto[]> {
  const { data } = await apiClient.get("/api/sessions/catalog", {
    params: season ? { season } : undefined,
  });
  return data;
}

export async function importSession(payload: SessionImportRequestDto): Promise<SessionDto> {
  const { data } = await apiClient.post("/api/sessions/import", payload);
  return data;
}

export async function getSession(sessionId: string): Promise<SessionDto> {
  const { data } = await apiClient.get(`/api/sessions/${sessionId}`);
  return data;
}

export async function listSessionEntries(sessionId: string): Promise<SessionEntryDto[]> {
  const { data } = await apiClient.get(`/api/sessions/${sessionId}/entries`);
  return data;
}

export async function listSessionCircuitCorners(
  sessionId: string,
): Promise<SessionCircuitCornerDto[]> {
  const { data } = await apiClient.get(`/api/sessions/${sessionId}/circuit-corners`);
  return data;
}

export async function listEntryLaps(
  sessionId: string,
  entryId: string,
): Promise<EntryLapDto[]> {
  const { data } = await apiClient.get(`/api/sessions/${sessionId}/entries/${entryId}/laps`);
  return data;
}

export async function listCarTelemetry(
  sessionId: string,
  entryId: string,
  query?: SessionTelemetryQuery,
): Promise<CarTelemetrySampleDto[]> {
  const { data } = await apiClient.get(
    `/api/sessions/${sessionId}/entries/${entryId}/telemetry/car`,
    {
      params: query,
    },
  );
  return data;
}

export async function listPositionTelemetry(
  sessionId: string,
  entryId: string,
  query?: SessionTelemetryQuery,
): Promise<PositionSampleDto[]> {
  const { data } = await apiClient.get(
    `/api/sessions/${sessionId}/entries/${entryId}/telemetry/position`,
    {
      params: query,
    },
  );
  return data;
}

export async function listSessionTicks(
  sessionId: string,
  query?: {
    offset?: number;
    limit?: number;
  },
): Promise<SessionTickDto[]> {
  const { data } = await apiClient.get(`/api/sessions/${sessionId}/ticks`, {
    params: query,
  });
  return data;
}

export async function listSessionTrackStatusEvents(
  sessionId: string,
  query?: {
    offset?: number;
    limit?: number;
  },
): Promise<SessionTrackStatusEventDto[]> {
  const { data } = await apiClient.get(`/api/sessions/${sessionId}/track-status-events`, {
    params: query,
  });
  return data;
}
