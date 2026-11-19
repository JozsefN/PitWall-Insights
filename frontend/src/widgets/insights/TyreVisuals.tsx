import type { DriverEstimate } from "../../features/race-insights/contracts";
import {
  formatEstimate,
  numericEstimate,
} from "../../features/race-insights/presentation";
import { formatLapTime } from "../../features/sessions/session-utils";
import { getCompoundLabel } from "../telemetry/utils/stint-analysis";

const loads = [
  ["tyre_thermal_load_index", "Thermal workload"],
  ["corner_load_index", "Cornering"],
  ["traction_load_index", "Traction"],
  ["wear_pressure_index", "Wear pressure"],
] as const;

export function TyreLoadProfile({
  metrics,
}: {
  metrics: DriverEstimate["metrics"];
}) {
  const scale = Math.max(
    100,
    ...loads.map(
      ([id]) => Math.ceil((numericEstimate(metrics[id]) ?? 0) / 25) * 25,
    ),
  );
  return (
    <figure className="tyre-load-profile">
      <figcaption>
        <strong>Workload profile</strong>
        <span>Model indices · scale 0–{scale}</span>
      </figcaption>
      <ul>
        {loads.map(([id, label]) => {
          const value = numericEstimate(metrics[id]);
          return (
            <li key={id}>
              <span>{label}</span>
              <div aria-hidden="true" data-missing={value == null}>
                {value != null ? (
                  <i
                    style={{ width: `${(Math.max(0, value) / scale) * 100}%` }}
                  />
                ) : null}
              </div>
              <strong>
                {value == null ? "Unavailable" : value.toFixed(1)}
              </strong>
            </li>
          );
        })}
      </ul>
    </figure>
  );
}

export function StintPaceVisual({ driver }: { driver: DriverEstimate }) {
  const observed = driver.pace_laps.filter(
    ({ time_s }) => Number.isFinite(time_s) && time_s > 0,
  );
  const last = observed.at(-1);
  if (!last)
    return (
      <p className="insight-empty">
        Comparable completed laps are needed to show pace changes.
      </p>
    );
  const laps = observed
    .filter(
      ({ stint_number, compound }) =>
        stint_number === last.stint_number && compound === last.compound,
    )
    .slice(-8);
  const best = Math.min(...laps.map(({ time_s }) => time_s));
  const scale = Math.max(0.2, ...laps.map(({ time_s }) => time_s - best));
  return (
    <figure className="stint-pace-visual">
      <figcaption>
        <strong>
          {last.stint_number != null
            ? `Stint ${last.stint_number} · ${getCompoundLabel(last.compound ?? null)}`
            : "Recent comparable laps"}
        </strong>
        <span>Slower than the best shown · seconds</span>
      </figcaption>
      <ol aria-label="Lap time differences">
        {laps.map((lap) => {
          const delta = lap.time_s - best;
          return (
            <li
              key={lap.lap}
              data-latest={lap === last}
              title={`Lap ${lap.lap}: ${formatLapTime(lap.time_s * 1000)}${lap.tyre_age == null ? "" : ` · tyre age ${lap.tyre_age}`}`}
            >
              <span>{delta > 0.0005 ? `+${delta.toFixed(2)}` : "Best"}</span>
              <div aria-hidden="true">
                <i style={{ height: `${(delta / scale) * 100}%` }} />
              </div>
              <strong>L{lap.lap}</strong>
            </li>
          );
        })}
      </ol>
      <p>
        Last shown <strong>{formatLapTime(last.time_s * 1000)}</strong> · Pace
        trend <strong>{formatEstimate(driver.metrics.stint_pace_slope)}</strong>
      </p>
    </figure>
  );
}
