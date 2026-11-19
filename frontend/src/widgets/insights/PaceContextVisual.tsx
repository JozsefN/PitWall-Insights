import type { DriverEstimate } from "../../features/race-insights/contracts";
import { numericEstimate } from "../../features/race-insights/presentation";
import { formatLapTime } from "../../features/sessions/session-utils";

export function PaceContextVisual({
  metrics,
}: {
  metrics: DriverEstimate["metrics"];
}) {
  const median = numericEstimate(metrics.recent_pace_s);
  const clear = numericEstimate(metrics.clean_air_reference_s);
  const changes = [
    {
      label: "Last clean lap vs earlier pace",
      delta: numericEstimate(metrics.last_lap_delta_s),
      note: "Needs at least two completed clean laps on the same set.",
    },
    {
      label: "Traffic laps vs low-traffic laps",
      delta: numericEstimate(metrics.traffic_correlated_loss_s),
      note: "Needs comparable laps with both low and sustained traffic exposure.",
    },
  ];
  const scale = Math.max(
    0.2,
    Math.ceil(
      Math.max(...changes.map(({ delta }) => Math.abs(delta ?? 0))) * 10,
    ) / 10,
  );
  return (
    <figure className="pace-context-visual">
      <figcaption>
        <strong>Lap-time differences</strong>
        <span>
          Recent clean pace{" "}
          <b>{median == null ? "Unavailable" : formatLapTime(median * 1000)}</b>
        </span>
      </figcaption>
      {changes.some(({ delta }) => delta != null) ? (
        <div className="pace-context-axis" aria-hidden="true">
          <span>{scale} s faster</span>
          <span>0</span>
          <span>{scale} s slower</span>
        </div>
      ) : null}
      <ul aria-label="Target lap or cohort compared with its reference">
        {changes.map(({ label, delta, note }) => (
          <li key={label}>
            <strong>{label}</strong>
            {delta == null ? (
              <small>{note}</small>
            ) : (
              <>
                <b>
                  {Math.abs(delta) < 0.005
                    ? "Level"
                    : `${Math.abs(delta).toFixed(2)} s ${delta < 0 ? "faster" : "slower"}`}
                </b>
                <div
                  className="pace-context-track"
                  aria-hidden="true"
                  data-faster={delta < 0}
                >
                  <i style={{ width: `${(Math.abs(delta) / scale) * 50}%` }} />
                </div>
              </>
            )}
          </li>
        ))}
      </ul>
      {clear != null ? (
        <p>
          Low-traffic reference <strong>{formatLapTime(clear * 1000)}</strong>
        </p>
      ) : null}
    </figure>
  );
}
