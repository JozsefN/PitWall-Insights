import { useSessionTimeLabel } from "../../features/sessions/SessionWorkspaceContext";
import { useReviewQuery } from "../../features/session-review/review-query";
import type { ReviewData } from "../../features/session-review/contracts";
import type { ReviewPanelId } from "./review-specs";
import { seconds } from "./format";
import { surfaceColours } from "../track-map/utils/circuit-overlays";
import {
  BattleGaps,
  FieldProjection,
  PitRejoin,
  PitTimingProfile,
  RacePaceChart,
  RivalPitWindows,
} from "./StrategyVisuals";

type Props = {
  panelId: ReviewPanelId;
  groups: ReviewData["groups"];
  name: (id: string) => string;
  contextId?: string;
};

export function ReviewContent({ panelId, groups, name, contextId }: Props) {
  const timeLabel = useSessionTimeLabel();
  if (panelId === "racecraft-review" && groups.racecraft)
    return (
      <>
        <h4>Active battles and closing trends</h4>
        <BattleGaps racecraft={groups.racecraft} name={name} />
        <h4>Estimated on-track passes</h4>
        {groups.racecraft.passes.length ? (
          <ol className="review-list">
            {[...groups.racecraft.passes]
              .reverse()
              .slice(0, 10)
              .map((pass) => (
                <li key={pass.id}>
                  <strong>
                    {name(pass.entry_id)} passed {name(pass.rival_entry_id)}
                  </strong>
                  <time>{timeLabel(pass.time_ms)}</time>
                </li>
              ))}
          </ol>
        ) : (
          <p>No sustained passes met the evidence rules in this window.</p>
        )}
      </>
    );
  if (panelId === "race-pace-forecast" && groups.pace) {
    const pace = groups.pace;
    return (
      <>
        <h4>Projection after {pace.horizon_laps} laps</h4>
        {pace.fuel_scenario_gain_s_per_lap ? (
          <small>
            Fuel scenario reduces each successive lap by{" "}
            {seconds(pace.fuel_scenario_gain_s_per_lap, 3)}. Every driver uses
            the same fuel assumption.
          </small>
        ) : null}
        <FieldProjection pace={pace} name={name} />
        <RacePaceChart rows={pace.drivers} name={name} />
        <details className="review-timing-evidence">
          <summary>Pace times and evidence</summary>
          <div className="review-scroll">
            <table>
              <thead>
                <tr>
                  <th>Driver</th>
                  <th>Median</th>
                  <th>Faster observed</th>
                  <th>Traffic</th>
                  <th>Stint trend</th>
                </tr>
              </thead>
              <tbody>
                {pace.drivers.map((row) => (
                  <tr key={row.entry_id}>
                    <th>
                      {name(row.entry_id)}
                      <small>{row.samples} laps</small>
                    </th>
                    <td>{seconds(row.median_pace_s)}</td>
                    <td>{seconds(row.faster_observed_pace_s)}</td>
                    <td>{seconds(row.traffic_pace_s)}</td>
                    <td>{seconds(row.observed_trend_s_per_lap)}/lap</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
        {pace.lapped_traffic_scenarios.length ? (
          <details>
            <summary>Lapped traffic scenarios</summary>
            <ol className="review-list">
              {pace.lapped_traffic_scenarios.slice(0, 10).map((row) => (
                <li key={`${row.entry_id}:${row.lapped_entry_id}`}>
                  <strong>
                    {name(row.entry_id)} → {name(row.lapped_entry_id)}
                  </strong>
                  <span>
                    {row.catch_after_laps.toFixed(1)} laps ·{" "}
                    {row.reference_shape.replace("_", " ")} · 0–
                    {row.delay_sensitivity_s[1]} s assumed
                  </span>
                </li>
              ))}
            </ol>
          </details>
        ) : null}
        <h4>Dry practice long runs</h4>
        {pace.practice_profiles.length ? (
          <ul className="review-list">
            {pace.practice_profiles.map((row) => (
              <li key={row.compound}>
                <strong>{row.compound}</strong>
                <span>
                  {row.runs} runs · longest{" "}
                  {row.longest_observed_clean_run_laps} laps
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p>
            Import same-weekend practice sessions to add qualifying long runs.
          </p>
        )}
        <small>
          Matched track evolution:{" "}
          {seconds(pace.track_evolution.pace_change_s_per_min, 3)}/min ·{" "}
          {pace.track_evolution.matched_drivers} drivers. Fuel, effort and
          rubber remain confounded.
        </small>
      </>
    );
  }
  if (panelId === "pit-benchmark" && groups.pit) {
    const pit = groups.pit;
    return (
      <>
        <PitRejoin pit={pit} name={name} />
        <PitTimingProfile pit={pit} />
        {pit.rival_windows.length ? (
          <RivalPitWindows rows={pit.rival_windows} name={name} />
        ) : null}
      </>
    );
  }
  if (panelId === "incident-reports" && groups.incidents)
    return (
      <>
        {groups.incidents.reports.length ? (
          <ol className="review-list">
            {[...groups.incidents.reports]
              .reverse()
              .slice(0, 20)
              .map((row, index) => (
                <li key={`${row.time_ms}:${index}`}>
                  <div>
                    <strong>{row.entry_ids.map(name).join(" / ")}</strong>
                    <small>{row.message}</small>
                  </div>
                  <time>{timeLabel(row.time_ms)}</time>
                </li>
              ))}
          </ol>
        ) : (
          <p>No matching race-control reports.</p>
        )}
        {groups.incidents.report_counts.length ? (
          <details>
            <summary>Reports by driver</summary>
            <ul className="review-list">
              {groups.incidents.report_counts.map((row) => (
                <li key={`${row.entry_id}:${row.report_kind}`}>
                  <strong>{name(row.entry_id)}</strong>
                  <span>
                    {row.count} · {row.report_kind.replaceAll("_", " ")}
                  </span>
                </li>
              ))}
            </ul>
          </details>
        ) : null}
        {groups.incidents.post_report_pace.length ? (
          <details>
            <summary>Same-stint pace around the report</summary>
            <ul className="review-list">
              {groups.incidents.post_report_pace.map((row) => (
                <li key={row.entry_id}>
                  <strong>{name(row.entry_id)}</strong>
                  <span>
                    {seconds(row.pace_change_s)} · {row.samples_before} before /{" "}
                    {row.samples_after} after
                  </span>
                </li>
              ))}
            </ul>
            <p>
              Traffic, tyres, weather and driver effort can contribute to the
              change.
            </p>
          </details>
        ) : null}
      </>
    );
  if (panelId === "weather-history" && groups.weather)
    return (
      <>
        <div className="review-stats">
          <div>
            <small>Rain flag</small>
            <strong>
              {groups.weather.current?.rain_reported == null
                ? "Unknown"
                : groups.weather.current.rain_reported
                  ? "Rain"
                  : "Clear"}
            </strong>
          </div>
          <div>
            <small>Wind</small>
            <strong>
              {groups.weather.current?.wind_speed_ms?.toFixed(1) ?? "—"} m/s
            </strong>
          </div>
          <div>
            <small>Track</small>
            <strong>
              {groups.weather.current?.track_temperature_c?.toFixed(1) ?? "—"}{" "}
              °C
            </strong>
          </div>
        </div>
        <div
          className="review-weather"
          aria-label="Historical wind direction and speed"
        >
          {groups.weather.timeline.slice(-18).map((row) => (
            <div
              key={row.time_ms}
              title={`${timeLabel(row.time_ms)} · wind bearing ${row.wind_direction_deg ?? "unknown"}°`}
              data-rain={Boolean(row.rain_reported)}
            >
              <span
                aria-hidden="true"
                style={{
                  transform: `rotate(${row.wind_direction_deg ?? 0}deg)`,
                }}
              >
                {row.wind_direction_deg == null ? "·" : "↑"}
              </span>
              <small>{row.wind_speed_ms?.toFixed(1) ?? "—"}</small>
            </div>
          ))}
        </div>
        <small>
          {groups.weather.reason} Arrows show reported bearings. Blue marks a
          rain report.
        </small>
      </>
    );
  if (panelId === "track-surface")
    return (
      <SurfaceMap fallback={groups.surface} name={name} contextId={contextId} />
    );
  return null;
}

function SurfaceMap({
  fallback,
  name,
  contextId,
}: {
  fallback: ReviewData["groups"]["surface"];
  name: Props["name"];
  contextId?: string;
}) {
  const timeLabel = useSessionTimeLabel();
  const query = useReviewQuery(["surface"], [], Boolean(contextId), {
    context_id: contextId,
  });
  const surface = contextId ? query.data?.groups.surface : fallback;
  if (query.isError && !query.data)
    return (
      <p role="alert">The profile could not be loaded for this session.</p>
    );
  if (query.isFetching && !query.data)
    return <p role="status">Loading track profile…</p>;
  if (!surface || (!surface.zones.length && !surface.recovery_points_m?.length))
    return (
      <p>
        {surface?.reason ??
          "Choose a calibrated strategy context in panel settings."}
      </p>
    );
  const points = [
    ...surface.zones.flatMap((zone) => zone.polygon_m),
    ...(surface.recovery_points_m ?? []),
  ];
  const x = points.map((point) => point[0]),
    y = points.map((point) => -point[1]);
  const minX = Math.min(...x),
    minY = Math.min(...y),
    width = Math.max(...x) - minX,
    height = Math.max(...y) - minY;
  return (
    <>
      <svg
        className="review-surface"
        role="img"
        aria-label="Registered track surface polygons"
        viewBox={`${minX - 20} ${minY - 20} ${width + 40} ${height + 40}`}
      >
        {surface.zones
          .filter((zone) => zone.kind !== "marshal_sector")
          .map((zone) => (
            <polygon
              key={zone.zone_id}
              points={zone.polygon_m.map(([a, b]) => `${a},${-b}`).join(" ")}
              fill={surfaceColours[zone.kind] ?? "#778899"}
            >
              <title>
                {zone.zone_id} · {zone.kind}
              </title>
            </polygon>
          ))}
        {surface.recovery_points_m?.map(([x, y], index) => (
          <circle
            key={index}
            cx={x}
            cy={-y}
            r={Math.max(3, width / 160)}
            fill="#182230"
            stroke={surfaceColours.recovery}
          >
            <title>Mapped recovery access {index + 1}</title>
          </circle>
        ))}
        {surface.cars.map((car) => (
          <circle
            key={car.entry_id}
            cx={car.x_m}
            cy={-car.y_m}
            r={Math.max(4, width / 120)}
            fill={
              car.beyond_mapped_track_candidate
                ? "var(--color-danger)"
                : "var(--color-text-primary)"
            }
          >
            <title>
              {name(car.entry_id)}
              {car.terrain ? ` · Mapped ${car.terrain}` : ""}
              {car.nearest_recovery_m != null
                ? ` · ${Math.round(car.nearest_recovery_m)} m straight line to mapped access`
                : ""}
            </title>
          </circle>
        ))}
      </svg>
      <small>
        {surface.reason}
        {contextId && query.data
          ? ` · Map at ${timeLabel(query.data.as_of_ms)}`
          : ""}
        {contextId && query.isFetching ? " · Updating" : ""}
      </small>
    </>
  );
}
