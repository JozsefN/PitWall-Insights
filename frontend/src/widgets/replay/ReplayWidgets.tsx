import type { SessionEntryDto } from "../../data/contracts/sessions.contracts";
import { WidgetCard } from "../shared/WidgetCard";
import { WidgetEmpty, WidgetError, WidgetLoading } from "../shared/WidgetState";
import { useWorkspaceCarTelemetryResource } from "../../features/sessions/session-data.hooks";
import { useSessionWorkspace } from "../../features/sessions/SessionWorkspaceContext";
import {
  findTelemetrySampleAtTime,
  getEntryAccent,
  getEntryDisplayName,
} from "../../features/sessions/session-utils";

export { ReplayTrackMapWidget } from "../track-map";

export function ReplayDriverCardsWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  void options;

  const workspace = useSessionWorkspace();
  const entryIds = workspace.selectedDriverIds;
  const telemetry = useWorkspaceCarTelemetryResource({
    entryIds,
    scope: "session",
    limit: 20000,
    enabled: entryIds.length > 0,
  });

  if (entryIds.length === 0) {
    return (
      <WidgetCard title="Replay Driver Cards">
        <WidgetEmpty message="Choose one or more drivers in the replay controls to see live-style telemetry cards." />
      </WidgetCard>
    );
  }

  if (telemetry.isError) {
    return (
      <WidgetCard title="Replay Driver Cards">
        <WidgetError />
      </WidgetCard>
    );
  }

  if (!telemetry.ready) {
    return (
      <WidgetCard title="Replay Driver Cards">
        <WidgetEmpty message={telemetry.waitMessage} />
      </WidgetCard>
    );
  }

  if (telemetry.isLoading) {
    return (
      <WidgetCard title="Replay Driver Cards">
        <WidgetLoading />
      </WidgetCard>
    );
  }

  const cards = entryIds
    .map((entryId, index) => {
      const entry = workspace.entries.find((candidate) => candidate.id === entryId);

      if (!entry) {
        return null;
      }

      const samples = telemetry.dataByEntryId[entryId] ?? [];
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
