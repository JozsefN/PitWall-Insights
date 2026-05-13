import { useQueries, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import {
  listCarTelemetry,
  listEntryLaps,
  listPositionTelemetry,
} from "../../data/api/sessions.api";
import type {
  CarTelemetrySampleDto,
  EntryLapDto,
  PositionSampleDto,
  SessionEntryDto,
  SessionTelemetryQuery,
} from "../../data/contracts/sessions.contracts";
import type { TelemetryKind, TelemetryScope } from "../../data/contracts/telemetry-materialization.contracts";
import {
  useEnsureTelemetryMaterializationQuery,
  useTelemetryMaterializationJobQuery,
} from "../../data/queries/telemetry-materialization.queries";
import { useSessionWorkspace } from "./SessionWorkspaceContext";

export type TelemetryEntryMode = "selected" | "all";
export type TelemetryScopeMode = TelemetryScope | "auto";

export type WorkspaceTelemetryResourceOptions = {
  entryIds?: string[];
  entryMode?: TelemetryEntryMode;
  scope?: TelemetryScopeMode;
  requireLap?: boolean;
  lapNumber?: number;
  offset?: number;
  limit?: number;
  sessionTimeFromMs?: number;
  sessionTimeToMs?: number;
  enabled?: boolean;
};

export type WorkspaceEntryResourceOptions = {
  entryIds?: string[];
  entryMode?: TelemetryEntryMode;
  enabled?: boolean;
};

export function useSelectedEntryLapsMap(enabled = true) {
  const workspace = useSessionWorkspace();
  return useEntryLapsMap(workspace.sessionId, workspace.selectedDriverIds, enabled);
}

export function useWorkspaceEntryLapsResource(options: WorkspaceEntryResourceOptions = {}) {
  const workspace = useSessionWorkspace();
  const resolved = resolveWorkspaceEntries(workspace, options);
  const laps = useEntryLapsMap(workspace.sessionId, resolved.entryIds, resolved.enabled);

  return {
    ...resolved,
    dataByEntryId: laps.dataByEntryId,
    isLoading: laps.isLoading,
    isError: laps.isError,
  };
}

export function useSelectedCarTelemetryMap(
  query?: SessionTelemetryQuery,
  enabled = true,
) {
  const workspace = useSessionWorkspace();
  return useCarTelemetryMap(workspace.sessionId, workspace.selectedDriverIds, query, enabled);
}

export function useSelectedPositionTelemetryMap(
  query?: SessionTelemetryQuery,
  enabled = true,
) {
  const workspace = useSessionWorkspace();
  return usePositionTelemetryMap(workspace.sessionId, workspace.selectedDriverIds, query, enabled);
}

export function useAllPositionTelemetryMap(
  query?: SessionTelemetryQuery,
  enabled = true,
) {
  const workspace = useSessionWorkspace();
  return usePositionTelemetryMap(
    workspace.sessionId,
    workspace.entries.map((entry) => entry.id),
    query,
    enabled,
  );
}

export function useWorkspaceCarTelemetryResource(options: WorkspaceTelemetryResourceOptions = {}) {
  const workspace = useSessionWorkspace();
  const resolved = resolveWorkspaceTelemetryResource(workspace, options);
  const materialization = useTelemetryMaterializationReadiness({
    entryIds: resolved.entryIds,
    kind: "car",
    scope: resolved.scope,
    lapNumber: resolved.lapNumber,
    enabled: resolved.enabled,
  });
  const telemetry = useCarTelemetryMap(
    workspace.sessionId,
    resolved.entryIds,
    resolved.query,
    resolved.enabled && materialization.ready,
  );

  return buildWorkspaceTelemetryResourceResult<CarTelemetrySampleDto>({
    ...resolved,
    ...materialization,
    dataByEntryId: telemetry.dataByEntryId,
    dataLoading: telemetry.isLoading,
    dataError: telemetry.isError,
    kind: "car",
  });
}

export function useWorkspacePositionTelemetryResource(options: WorkspaceTelemetryResourceOptions = {}) {
  const workspace = useSessionWorkspace();
  const resolved = resolveWorkspaceTelemetryResource(workspace, options);
  const materialization = useTelemetryMaterializationReadiness({
    entryIds: resolved.entryIds,
    kind: "position",
    scope: resolved.scope,
    lapNumber: resolved.lapNumber,
    enabled: resolved.enabled,
  });
  const telemetry = usePositionTelemetryMap(
    workspace.sessionId,
    resolved.entryIds,
    resolved.query,
    resolved.enabled && materialization.ready,
  );

  return buildWorkspaceTelemetryResourceResult<PositionSampleDto>({
    ...resolved,
    ...materialization,
    dataByEntryId: telemetry.dataByEntryId,
    dataLoading: telemetry.isLoading,
    dataError: telemetry.isError,
    kind: "position",
  });
}

export function useTelemetryMaterializationReadiness({
  entryIds,
  kind,
  scope,
  lapNumber,
  enabled,
}: {
  entryIds: string[];
  kind: TelemetryKind;
  scope: TelemetryScope;
  lapNumber?: number;
  enabled: boolean;
}) {
  const workspace = useSessionWorkspace();
  const queryClient = useQueryClient();
  const request = enabled
    ? {
        session_id: workspace.sessionId,
        entry_ids: entryIds,
        kinds: [kind],
        scope,
        lap_number: scope === "lap" ? lapNumber : undefined,
      }
    : null;
  const ensureQuery = useEnsureTelemetryMaterializationQuery(request, enabled);
  const jobQuery = useTelemetryMaterializationJobQuery(ensureQuery.data?.job_id, Boolean(ensureQuery.data?.job_id));
  const completed = jobQuery.data?.status === "completed";
  const jobId = ensureQuery.data?.job_id;

  useEffect(() => {
    if (!jobId) {
      return;
    }

    void queryClient.invalidateQueries({ queryKey: ["telemetry-materialization", "jobs"] });
  }, [jobId, queryClient]);

  useEffect(() => {
    if (!completed) {
      return;
    }

    void queryClient.invalidateQueries({ queryKey: ["sessions", workspace.sessionId] });
    void queryClient.invalidateQueries({ queryKey: ["sessions", workspace.sessionId, "entries"] });
    void queryClient.invalidateQueries({ queryKey: ["telemetry-materialization", "ensure"] });
    void queryClient.invalidateQueries({ queryKey: ["telemetry-materialization", "jobs"] });
  }, [completed, queryClient, workspace.sessionId]);

  return {
    ready: workspace.session.telemetry_status === "loaded" || ensureQuery.data?.ready === true || completed,
    isError: ensureQuery.isError || jobQuery.data?.status === "failed" || jobQuery.isError,
    isPreparing: enabled && !(workspace.session.telemetry_status === "loaded" || ensureQuery.data?.ready === true || completed),
    stage: jobQuery.data?.progress_stage ?? (ensureQuery.isFetching ? "queued" : undefined),
  };
}

function resolveWorkspaceTelemetryResource(
  workspace: ReturnType<typeof useSessionWorkspace>,
  options: WorkspaceTelemetryResourceOptions,
) {
  const resolvedEntries = resolveWorkspaceEntries(workspace, options);
  const scope = resolveTelemetryScope(options.scope ?? "auto", workspace.lapSelection);
  const lapNumber =
    scope === "lap"
      ? options.lapNumber ?? (workspace.lapSelection === "all" ? undefined : workspace.lapSelection)
      : undefined;
  const hasRequiredLap = !options.requireLap || lapNumber != null;
  const enabled = resolvedEntries.enabled && hasRequiredLap && (scope === "session" || lapNumber != null);
  const query: SessionTelemetryQuery = {
    offset: options.offset,
    limit: options.limit,
    lap_number: scope === "lap" ? lapNumber : undefined,
    session_time_from_ms: options.sessionTimeFromMs,
    session_time_to_ms: options.sessionTimeToMs,
  };

  return {
    entryIds: resolvedEntries.entryIds,
    entries: resolvedEntries.entries,
    scope,
    lapNumber,
    query,
    enabled,
  };
}

function resolveWorkspaceEntries(
  workspace: ReturnType<typeof useSessionWorkspace>,
  options: WorkspaceEntryResourceOptions,
) {
  const entriesById = new Map(workspace.entries.map((entry) => [entry.id, entry]));
  const entryIds = Array.from(
    new Set(
      options.entryIds ??
        (options.entryMode === "all"
          ? workspace.entries.map((entry) => entry.id)
          : workspace.selectedDriverIds),
    ),
  ).filter((entryId) => entriesById.has(entryId));
  const entries = entryIds
    .map((entryId) => entriesById.get(entryId))
    .filter((entry): entry is SessionEntryDto => Boolean(entry));

  return {
    entryIds,
    entries,
    enabled: (options.enabled ?? true) && entryIds.length > 0,
  };
}

function resolveTelemetryScope(scope: TelemetryScopeMode, lapSelection: number | "all"): TelemetryScope {
  if (scope !== "auto") {
    return scope;
  }

  return lapSelection === "all" ? "session" : "lap";
}

function buildWorkspaceTelemetryResourceResult<TSample>({
  entryIds,
  entries,
  scope,
  lapNumber,
  query,
  enabled,
  ready,
  isError,
  isPreparing,
  stage,
  dataByEntryId,
  dataLoading,
  dataError,
  kind,
}: {
  entryIds: string[];
  entries: SessionEntryDto[];
  scope: TelemetryScope;
  lapNumber?: number;
  query: SessionTelemetryQuery;
  enabled: boolean;
  ready: boolean;
  isError: boolean;
  isPreparing: boolean;
  stage?: string;
  dataByEntryId: Record<string, TSample[]>;
  dataLoading: boolean;
  dataError: boolean;
  kind: TelemetryKind;
}) {
  return {
    entryIds,
    entries,
    scope,
    lapNumber,
    query,
    enabled,
    ready,
    isPreparing,
    stage,
    waitMessage: getTelemetryResourceWaitMessage(kind, stage),
    dataByEntryId,
    isLoading: dataLoading,
    isError: isError || dataError,
  };
}

function getTelemetryResourceWaitMessage(kind: TelemetryKind, stage?: string) {
  const label = kind === "car" ? "Car telemetry" : "Position telemetry";

  if (stage === "loading_source") {
    return `${label} is being fetched for this selection. Cached slices stay reusable across modes.`;
  }

  if (stage === "normalizing") {
    return `${label} is being shaped for the selected drivers and scope.`;
  }

  if (stage === "persisting") {
    return `${label} is being written to the session cache.`;
  }

  return `${label} is being prepared for this selection.`;
}

function useEntryLapsMap(sessionId: string, entryIds: string[], enabled: boolean) {
  const results = useQueries({
    queries: entryIds.map((entryId) => ({
      queryKey: ["sessions", sessionId, "entries", entryId, "laps"],
      queryFn: () => listEntryLaps(sessionId, entryId),
      enabled,
    })),
  });

  return {
    dataByEntryId: Object.fromEntries(
      entryIds.map((entryId, index) => [entryId, results[index]?.data ?? []]),
    ) as Record<string, EntryLapDto[]>,
    isLoading: results.some((result) => result.isLoading),
    isError: results.some((result) => result.isError),
  };
}

function useCarTelemetryMap(
  sessionId: string,
  entryIds: string[],
  query: SessionTelemetryQuery | undefined,
  enabled: boolean,
) {
  const results = useQueries({
    queries: entryIds.map((entryId) => ({
      queryKey: ["sessions", sessionId, "entries", entryId, "telemetry", "car", query],
      queryFn: () => listCarTelemetry(sessionId, entryId, query),
      enabled,
    })),
  });

  return {
    dataByEntryId: Object.fromEntries(
      entryIds.map((entryId, index) => [entryId, results[index]?.data ?? []]),
    ) as Record<string, CarTelemetrySampleDto[]>,
    isLoading: results.some((result) => result.isLoading),
    isError: results.some((result) => result.isError),
  };
}

function usePositionTelemetryMap(
  sessionId: string,
  entryIds: string[],
  query: SessionTelemetryQuery | undefined,
  enabled: boolean,
) {
  const results = useQueries({
    queries: entryIds.map((entryId) => ({
      queryKey: ["sessions", sessionId, "entries", entryId, "telemetry", "position", query],
      queryFn: () => listPositionTelemetry(sessionId, entryId, query),
      enabled,
    })),
  });

  return {
    dataByEntryId: Object.fromEntries(
      entryIds.map((entryId, index) => [entryId, results[index]?.data ?? []]),
    ) as Record<string, PositionSampleDto[]>,
    isLoading: results.some((result) => result.isLoading),
    isError: results.some((result) => result.isError),
  };
}
