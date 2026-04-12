import { useQueries } from "@tanstack/react-query";
import { listCarTelemetry } from "../../data/api/sessions.api";
import type { SessionEntryDto } from "../../data/contracts/sessions.contracts";
import { WidgetCard } from "../shared/WidgetCard";
import { WidgetEmpty, WidgetError, WidgetLoading } from "../shared/WidgetState";
import { useAllPositionTelemetryMap } from "../../features/sessions/session-data.hooks";
import { useSessionWorkspace } from "../../features/sessions/SessionWorkspaceContext";
import {
  buildReplayTrackViewBox,
  buildTrackPoints,
  downsamplePoints,
  findPositionSampleAtTime,
  findTelemetrySampleAtTime,
  formatSessionClock,
  getEntryAccent,
  getEntryDisplayName,
} from "../../features/sessions/session-utils";

export function ReplayTrackMapWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  void options;

  const workspace = useSessionWorkspace();
  const positions = useAllPositionTelemetryMap({ limit: 20000 }, workspace.entries.length > 0);

  if (workspace.entries.length === 0) {
    return (
      <WidgetCard title="Replay Track Map">
        <WidgetEmpty message="No session entries were available for replay mode." />
      </WidgetCard>
    );
  }

  if (positions.isLoading) {
    return (
      <WidgetCard title="Replay Track Map">
        <WidgetLoading />
      </WidgetCard>
    );
  }

  if (positions.isError) {
    return (
      <WidgetCard title="Replay Track Map">
        <WidgetError />
      </WidgetCard>
    );
  }

  const traces = workspace.entries.map((entry, index) => ({
    entry,
    color: getEntryAccent(entry, index),
    points: downsamplePoints(buildTrackPoints(positions.dataByEntryId[entry.id] ?? []), 220),
    currentSample: findPositionSampleAtTime(positions.dataByEntryId[entry.id] ?? [], workspace.replay.currentTimeMs),
  }));
  const outlinePoints = traces.find((trace) => trace.points.length > 0)?.points ?? [];
  const livePoints = traces.filter((trace) => trace.currentSample?.x != null && trace.currentSample?.y != null);

  if (outlinePoints.length === 0) {
    return (
      <WidgetCard title="Replay Track Map">
        <WidgetEmpty message="Position telemetry was not available for replay mode." />
      </WidgetCard>
    );
  }

  const viewBox = buildReplayTrackViewBox(outlinePoints);

  return (
    <WidgetCard
      title="Replay Track Map"
      description={`Current replay time · ${formatSessionClock(workspace.replay.currentTimeMs)}`}
    >
      <div className="telemetry-chart telemetry-chart--track">
        <svg viewBox={viewBox} className="telemetry-track-map">
          <path
            d={outlinePoints.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ")}
            fill="none"
            stroke="rgba(255,255,255,0.16)"
            strokeWidth="14"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {livePoints.map((trace) => (
            <circle
              key={trace.entry.id}
              cx={trace.currentSample?.x ?? 0}
              cy={trace.currentSample?.y ?? 0}
              r="18"
              fill={trace.color}
              stroke="rgba(11, 13, 18, 0.9)"
              strokeWidth="6"
            />
          ))}
        </svg>
        <div className="telemetry-chart__legend">
          {livePoints.slice(0, 10).map((trace) => (
            <span key={trace.entry.id} className="telemetry-driver-chip">
              <i style={{ backgroundColor: trace.color }} />
              {getEntryDisplayName(trace.entry)}
            </span>
          ))}
        </div>
      </div>
    </WidgetCard>
  );
}

export function ReplayDriverCardsWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  void options;

  const workspace = useSessionWorkspace();
  const entryIds =
    workspace.selectedDriverIds.length > 0
      ? workspace.selectedDriverIds
      : workspace.entries.slice(0, 4).map((entry) => entry.id);

  const telemetryQueries = useQueries({
    queries: entryIds.map((entryId) => ({
      queryKey: ["sessions", workspace.sessionId, "entries", entryId, "telemetry", "car", "replay"],
      queryFn: () => listCarTelemetry(workspace.sessionId, entryId, { limit: 20000 }),
      enabled: entryIds.length > 0,
    })),
  });

  if (entryIds.length === 0) {
    return (
      <WidgetCard title="Replay Driver Cards">
        <WidgetEmpty message="Choose drivers or import a session with entries to see replay telemetry." />
      </WidgetCard>
    );
  }

  if (telemetryQueries.some((query) => query.isLoading)) {
    return (
      <WidgetCard title="Replay Driver Cards">
        <WidgetLoading />
      </WidgetCard>
    );
  }

  if (telemetryQueries.some((query) => query.isError)) {
    return (
      <WidgetCard title="Replay Driver Cards">
        <WidgetError />
      </WidgetCard>
    );
  }

  const cards = entryIds
    .map((entryId, index) => {
      const entry = workspace.entries.find((candidate) => candidate.id === entryId);

      if (!entry) {
        return null;
      }

      const samples = telemetryQueries[index]?.data ?? [];
      const currentSample = findTelemetrySampleAtTime(samples, workspace.replay.currentTimeMs);

      return {
        entry,
        currentSample,
        accent: getEntryAccent(entry, index),
      };
    })
    .filter((card): card is { entry: SessionEntryDto; currentSample: ReturnType<typeof findTelemetrySampleAtTime>; accent: string } => card !== null);

  return (
    <WidgetCard
      title="Replay Driver Cards"
      description="Live-style telemetry cards driven by the replay clock."
    >
      <div className="replay-driver-grid">
        {cards.map((card) => (
          <article
            key={card.entry.id}
            className="replay-driver-card"
            style={{ borderColor: `${card.accent}55` }}
          >
            <header className="replay-driver-card__header">
              <div>
                <span className="replay-driver-card__eyebrow">{card.entry.team_name ?? "Team"}</span>
                <h4>{getEntryDisplayName(card.entry)}</h4>
              </div>
              <span className="replay-driver-card__number">#{card.entry.car_number}</span>
            </header>
            <div className="replay-driver-card__stats">
              <div>
                <span>Speed</span>
                <strong>{card.currentSample?.speed_kph != null ? `${Math.round(card.currentSample.speed_kph)} kph` : "--"}</strong>
              </div>
              <div>
                <span>Gear</span>
                <strong>{card.currentSample?.gear ?? "--"}</strong>
              </div>
              <div>
                <span>Throttle</span>
                <strong>{card.currentSample?.throttle_pct != null ? `${Math.round(card.currentSample.throttle_pct)}%` : "--"}</strong>
              </div>
              <div>
                <span>Brake</span>
                <strong>{card.currentSample?.brake_on ? "On" : "Off"}</strong>
              </div>
            </div>
          </article>
        ))}
      </div>
    </WidgetCard>
  );
}
