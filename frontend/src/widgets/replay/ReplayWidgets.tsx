import { useState, type CSSProperties } from "react";
import type {
  CarTelemetrySampleDto,
  SessionEntryDto,
} from "../../data/contracts/sessions.contracts";
import {
  useReplayTime,
  useSessionWorkspace,
} from "../../features/sessions/SessionWorkspaceContext";
import { useWorkspaceReplayData } from "../../features/sessions/workspace-replay-data";
import {
  getEntryAccent,
  getEntryDisplayName,
} from "../../features/sessions/session-utils";
import { DriverCard } from "../driver-cards/DriverCardIdentity";
import { replayCardData } from "../driver-cards/replay-card-data";
import { ChartDriverPicker } from "../telemetry/components/ChartDriverPicker";
import { WidgetCard } from "../shared/WidgetCard";
import { WidgetEmpty, WidgetError, WidgetLoading } from "../shared/WidgetState";

export { ReplayTrackMapWidget } from "../track-map";

export function ReplayDriverCardsWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  const title =
    typeof options?.title === "string" ? options.title : "Replay Driver Cards";
  const { selectedEntries } = useSessionWorkspace();
  const { car: telemetry } = useWorkspaceReplayData();
  const [selection, setSelection] = useState("");
  const focus = selectedEntries.some(({ id }) => id === selection)
    ? selection
    : "";
  const chosen = selectedEntries.filter(({ id }) => !focus || id === focus);
  return (
    <WidgetCard
      title={title}
      actions={
        <ChartDriverPicker
          drivers={selectedEntries.map((entry) => ({
            entry,
            id: entry.id,
            label: getEntryDisplayName(entry),
          }))}
          value={focus}
          onChange={setSelection}
        />
      }
    >
      {selectedEntries.length === 0 ? (
        <WidgetEmpty message="Choose drivers to follow their speed and pedal inputs." />
      ) : telemetry.isError ? (
        <WidgetError message={telemetry.errorMessage} />
      ) : !telemetry.ready ? (
        <WidgetEmpty message={telemetry.waitMessage} />
      ) : telemetry.isLoading ? (
        <WidgetLoading />
      ) : (
        <ReplayCards entries={chosen} samples={telemetry.dataByEntryId} />
      )}
    </WidgetCard>
  );
}

function ReplayCards({
  entries,
  samples,
}: {
  entries: SessionEntryDto[];
  samples: Record<string, CarTelemetrySampleDto[]>;
}) {
  const timeMs = useReplayTime();
  return (
    <div className="driver-card-grid replay-driver-grid">
      {entries.map((entry) => {
        const live = replayCardData(samples[entry.id] ?? [], timeMs);
        const sample = live.sample;
        const throttle = sample?.throttle_pct;
        const brake = sample?.brake_on;
        return (
          <DriverCard
            key={entry.id}
            className="replay-driver-card"
            identity={{
              entryId: entry.id,
              name: entry.driver_name || getEntryDisplayName(entry),
              carNumber: entry.car_number,
              team: entry.team_name,
              accent: getEntryAccent(entry),
              headshot: entry.headshot_url,
            }}
          >
            <div className="driver-card__speed" data-fresh={Boolean(sample)}>
              <div>
                <strong>
                  {sample?.speed_kph == null
                    ? "—"
                    : Math.round(sample.speed_kph)}
                </strong>{" "}
                <small>km/h</small>
              </div>
              <div className="driver-card__gear">
                <small>Gear</small>
                <strong>{sample?.gear ?? "—"}</strong>
              </div>
            </div>
            <figure className="driver-card__trace">
              <svg
                viewBox="0 0 160 40"
                preserveAspectRatio="none"
                role="img"
                aria-label={
                  live.hasSpeedTrace
                    ? "Ground speed over the last 10 seconds, on a 0 to 400 kilometres per hour scale"
                    : "No continuous speed trace in the last 10 seconds"
                }
              >
                <path
                  className="driver-card__trace-grid"
                  d="M0 4H160M0 20H160M0 36H160M80 4V36"
                />
                {live.hasSpeedTrace ? (
                  <path
                    className="driver-card__speed-path"
                    d={live.speedPath}
                  />
                ) : null}
              </svg>
              <figcaption>
                {sample
                  ? "Last 10 s · 0–400 km/h"
                  : live.hasPriorSample
                    ? "No recent telemetry"
                    : "Waiting for first sample"}
              </figcaption>
            </figure>
            <div className="driver-card__pedals">
              <div className="driver-card__throttle">
                <span>
                  Throttle{" "}
                  <strong>
                    {throttle == null ? "—" : `${Math.round(throttle)}%`}
                  </strong>
                </span>
                <div
                  className="driver-card__meter"
                  aria-hidden="true"
                  data-missing={throttle == null}
                  style={
                    {
                      "--pedal-fill": `${Math.max(0, Math.min(100, throttle ?? 0))}%`,
                    } as CSSProperties
                  }
                >
                  <i />
                </div>
              </div>
              <span
                className="driver-card__brake"
                data-braking={brake === true}
              >
                Brake{" "}
                <strong>{brake == null ? "—" : brake ? "On" : "Off"}</strong>
              </span>
            </div>
          </DriverCard>
        );
      })}
    </div>
  );
}
