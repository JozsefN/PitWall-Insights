import { DriverSelect } from "../../components/DriverSelect";
import { driverOption } from "../../components/driver-select-options";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../../data/api/client";
import { useRaceEstimationResource } from "../../features/race-insights/race-estimation-context";
import {
  filterEvents,
  formatEstimate,
  notificationCapacity,
} from "../../features/race-insights/presentation";
import { useSessionTimeLabel } from "../../features/sessions/SessionWorkspaceContext";
import type {
  DriverEstimate,
  EstimateValue,
  RaceEvent,
} from "../../features/race-insights/contracts";
import { WidgetCard } from "../shared/WidgetCard";
import { useWidgetSize } from "../shared/widget-size";
import { insightPanelGuide, insightPanels } from "./panel-specs";
import { StintPaceVisual, TyreLoadProfile } from "./TyreVisuals";
import { PaceContextVisual } from "./PaceContextVisual";
import type { InsightPanelId } from "./panel-specs";
import "./insights.css";

type Options = Record<string, unknown>;
type Definition = {
  metric_id: string;
  label: string;
  formula: string;
  requires?: string[];
};
const unavailableLabels = {
  missing_data: "Missing data",
  outside_window: "Outside race window",
  not_applicable: "Doesn't apply here",
};

function explainUnavailable(metric?: EstimateValue, definition?: Definition) {
  if (
    metric?.reason &&
    !metric.reason.startsWith("Required observations or comparable context")
  )
    return metric.reason;
  return definition?.requires?.length
    ? `Needs ${definition.requires.join(", ")}.`
    : "No comparable observations at this time.";
}
const phaseLabels: Record<string, string> = {
  "1": "Green",
  "2": "Yellow",
  "4": "Safety car",
  "5": "Red flag",
  "6": "Virtual safety car",
  "7": "VSC ending",
};

function Metric({
  id,
  metric,
  definition,
  options,
}: {
  id: string;
  metric?: EstimateValue;
  definition?: Definition;
  options: Options;
}) {
  const value = formatEstimate(metric);
  const available = metric?.status === "available";
  return (
    <details className="insight-metric" data-method={metric?.method}>
      <summary>
        <span>{definition?.label ?? id.replaceAll("_", " ")}</span>
        <strong>{value}</strong>
        {!available ? (
          <small className="insight-unavailable">
            <b>
              {metric?.unavailable_cause
                ? unavailableLabels[metric.unavailable_cause]
                : "Needs evidence"}
            </b>{" "}
            {explainUnavailable(metric, definition)}
          </small>
        ) : null}
        {available ? (
          <small>
            {metric?.method === "scenario"
              ? "Scenario"
              : metric?.method === "index"
                ? "Relative index"
                : metric?.method === "observed"
                  ? "Reported"
                  : "Calculated"}
            {options.showSupport !== false && metric?.status === "available"
              ? ` · support ${Math.round(metric.support * 100)}%`
              : ""}
          </small>
        ) : null}
        {options.showRanges !== false &&
        metric?.lower != null &&
        metric.upper != null ? (
          <small>
            {metric.lower.toFixed(2)}–{metric.upper.toFixed(2)} {metric.unit} ·{" "}
            {metric.uncertainty?.replaceAll("_", " ") ?? "sensitivity"}
          </small>
        ) : null}
      </summary>
      <p>
        {available
          ? (metric.reason ?? definition?.formula)
          : definition?.formula}
      </p>
      <small>
        Support describes evidence coverage, not the probability that an
        estimate is correct.
      </small>
    </details>
  );
}

function Sparkline({
  driver,
  field,
  label,
}: {
  driver: DriverEstimate;
  field: string;
  label: string;
}) {
  const timeLabel = useSessionTimeLabel();
  const points = driver.series.filter(
    (row) => typeof row[field] === "number",
  ) as Array<Record<string, number>>;
  if (points.length < 2)
    return (
      <p className="insight-empty">
        More continuous observations are needed for {label.toLowerCase()}.
      </p>
    );
  const values = points.map((row) => row[field]);
  const min = Math.min(...values),
    max = Math.max(...values);
  const start = points[0].time_ms,
    span = Math.max(1, points.at(-1)!.time_ms - start);
  // Break the line at missing samples, rather than drawing through source outages.
  const path = points
    .map((row, index) => {
      const command =
        index === 0 || row.time_ms - points[index - 1].time_ms > 4000
          ? "M"
          : "L";
      return `${command}${10 + ((row.time_ms - start) / span) * 380},${90 - ((row[field] - min) / Math.max(0.01, max - min)) * 70}`;
    })
    .join(" ");
  return (
    <figure className="insight-chart">
      <figcaption>
        {label}
        <span>
          {min.toFixed(1)} – {max.toFixed(1)}
        </span>
      </figcaption>
      <svg
        viewBox="0 0 400 110"
        role="img"
        aria-label={`${label}, from ${min.toFixed(1)} to ${max.toFixed(1)}`}
      >
        <path d="M10 90H390M10 55H390M10 20H390" stroke="#304154" fill="none" />
        <path
          d={path}
          fill="none"
          stroke="var(--insight-accent)"
          strokeWidth="2.5"
        />
      </svg>
      <small>
        {timeLabel(start)} – {timeLabel(start + span)} · trailing window
      </small>
    </figure>
  );
}

function EventList({
  events,
  name,
}: {
  events: RaceEvent[];
  name: (id: string | null) => string;
}) {
  const timeLabel = useSessionTimeLabel();
  return (
    <ol className="insight-events" aria-label="Recent race messages">
      {events.map((event) => (
        <li key={event.id} data-severity={event.severity}>
          <details>
            <summary>
              <div className="insight-event-meta">
                <time>{timeLabel(event.time_ms)}</time>
                <span>
                  {event.classification === "candidate"
                    ? "Estimate candidate"
                    : event.classification}{" "}
                  · {event.severity}
                </span>
              </div>
              <strong>
                {event.entry_id ? `${name(event.entry_id)} · ` : ""}
                {event.title}
              </strong>
            </summary>
            <p>{event.detail}</p>
            {event.alternatives.length ? (
              <p>Other explanations: {event.alternatives.join("; ")}</p>
            ) : null}
            <dl className="insight-evidence">
              {Object.entries(event.evidence).map(([key, value]) => (
                <div key={key}>
                  <dt>{key.replaceAll("_", " ")}</dt>
                  <dd>
                    {typeof value === "object"
                      ? JSON.stringify(value)
                      : String(value)}
                  </dd>
                </div>
              ))}
            </dl>
            <small>
              Evidence support: {Math.round(event.support * 100)}%. Candidates
              are not confirmed incidents or lockups.
            </small>
          </details>
        </li>
      ))}
    </ol>
  );
}

export function InsightWidget({
  panelId,
  options = {},
}: {
  panelId: InsightPanelId;
  options?: Options;
}) {
  const resource = useRaceEstimationResource();
  const timeLabel = useSessionTimeLabel();
  const { workspace, query } = resource;
  const size = useWidgetSize();
  const [focusId, setFocusId] = useState("");
  const [compareId, setCompareId] = useState("");
  const catalog = useQuery({
    queryKey: ["race-estimates", "catalog"],
    queryFn: async () =>
      (
        await apiClient.get<{ metrics: Definition[] }>(
          "/api/feature-metrics/race-estimates/catalog",
        )
      ).data,
    staleTime: Infinity,
  });
  const definitions = Object.fromEntries(
    (catalog.data?.metrics ?? []).map((item) => [item.metric_id, item]),
  );
  const data = query.data;
  const drivers = data?.drivers ?? [];
  const focus =
    drivers.find((driver) => driver.entry_id === focusId) ?? drivers[0];
  const other =
    drivers.find(
      (driver) =>
        driver.entry_id === compareId && driver.entry_id !== focus?.entry_id,
    ) ?? drivers.find((driver) => driver !== focus);
  const spec = insightPanels[panelId];
  const metrics = spec.metrics.filter(
    (id) =>
      workspace.mode === "simulation" ||
      ![
        "wear_pressure_index",
        "traffic_time_pct",
        "peak_deceleration_g",
        "tyre_thermal_load_index",
        "telemetry_coverage_pct",
      ].includes(id),
  );
  const showPaceChart = panelId === "stint-performance" || panelId === "pace-context";
  const showMetricDisclosure = panelId === "tyre-workload" || showPaceChart;
  const metricGrid = focus ? (
    <div className="insight-metrics">
      {metrics.map((id) => (
        <Metric key={id} id={id} metric={focus.metrics[id]} definition={definitions[id]} options={options} />
      ))}
    </div>
  ) : null;
  const name = (id: string | null) => {
    const entry = workspace.entries.find((item) => item.id === id);
    return (
      (options.includeCandidates === false ? entry?.driver_name : entry?.driver_abbreviation) ??
      entry?.driver_name ??
      entry?.driver_abbreviation ??
      (entry ? `#${entry.car_number}` : "Race control")
    );
  };
  const capacity = notificationCapacity(size.height, options.maxItems);
  const events = filterEvents(
    data?.events ?? [],
    options,
    workspace.selectedDriverIds,
    resource.currentTime,
  );
  const incidentEvents = events.filter((event) =>
    [
      "possible_incident",
      "stopped_car",
      "braking_anomaly",
      "traction_disruption",
      "yellow_flag",
      "safety_car",
      "red_flag",
    ].includes(event.kind),
  );
  const showDriver = panelId !== "race-notifications";
  const reportsOnly = !showDriver && options.includeCandidates === false;
  const pairs = (data?.pairs ?? []).filter(
    (pair) =>
      !workspace.selectedDriverIds.length ||
      workspace.selectedDriverIds.includes(pair.follower_id) ||
      workspace.selectedDriverIds.includes(pair.ahead_id),
  );
  return (
    <WidgetCard
      title={typeof options.title === "string" ? options.title : spec.title}
      description={size.short ? undefined : reportsOnly ? "Flags, pit stops and passes from race timing and race control." : spec.description}
      actions={
        showDriver && drivers.length > 1 ? (
          <DriverSelect
            aria-label={`${spec.title} driver`}
            value={focus?.entry_id ?? ""}
            onChange={setFocusId}
            options={drivers.map((driver) => {
              const entry = workspace.entries.find((item) => item.id === driver.entry_id);
              return entry ? driverOption(entry) : { value: driver.entry_id, label: name(driver.entry_id) };
            })}
          />
        ) : undefined
      }
    >
      <div className="insight-panel" data-insight-panel={panelId}>
        <div className="insight-context">
          <span>
            {workspace.mode === "simulation" ? "Replay" : "Lookback"} ·{" "}
            {timeLabel(data?.as_of_ms ?? resource.cutoff)}
          </span>
          <span>
            {data
              ? (phaseLabels[String(data.conditions.track_status)] ??
                "Track state unknown")
              : "Loading context"}
            <span
              className="snapshot-refresh-status"
              data-visible={query.isFetching && Boolean(data)}
            >
              {" · Updating"}
            </span>
          </span>
        </div>
        <details className="insight-help">
          <summary>When to use this panel</summary>
          <p>{insightPanelGuide[panelId]}</p>
        </details>
        {query.isError ? (
          <div role="alert" className="insight-empty">
            <strong>Analysis request failed.</strong> {resource.errorMessage}
            <button
              className="button-secondary"
              onClick={() => void query.refetch()}
            >
              Retry analysis
            </button>
          </div>
        ) : null}
        {!data && !query.isError ? (
          <p role="status">Loading race analysis…</p>
        ) : null}
        {resource.preparing ? (
          <p className="insight-notice" role="status">
            Preparing selected drivers’ telemetry. Timing and reported events
            remain available.
          </p>
        ) : null}
        {resource.telemetryError ? (
          <p className="insight-notice">
            Some telemetry could not be prepared. Open session data loading to
            retry; unsupported estimates remain unavailable.
          </p>
        ) : null}
        {panelId === "race-notifications" && data ? (
          <>
            <div className="insight-feed-summary">
              <span>
                {events.length
                  ? `Latest ${Math.min(capacity, events.length)} of ${events.length}`
                  : "No matching messages"}
              </span>
              <span>
                {options.includeCandidates === false
                  ? "Race control and timing"
                  : "Candidates included"}
              </span>
            </div>
            <EventList events={events.slice(0, capacity)} name={name} />
            {!events.length ? (
              <p className="insight-empty">
                {reportsOnly
                  ? "There are no recent race updates at the selected time."
                  : "No recent events match this panel's filters."}
              </p>
            ) : null}
            {data.events_truncated ? (
              <small>
                The server event limit was reached; older messages are omitted.
              </small>
            ) : null}
          </>
        ) : null}
        {data && showDriver && !focus ? (
          <p className="insight-empty">
            Select a driver to explore supported metrics.
          </p>
        ) : null}
        {data && focus && showDriver ? (
          <>
            <div className="insight-driver">
              <span className="insight-driver-dot" />
              <strong>{name(focus.entry_id)}</strong>
              <small>
                {focus.ahead_entry_id
                  ? `Ahead: ${name(focus.ahead_entry_id)}`
                  : "No fresh car-ahead report"}
              </small>
            </div>
            {panelId === "driver-comparison" ? (
              <>
                <label className="insight-compare-label">
                  Compare with{" "}
                  <DriverSelect
                    aria-label="Comparison driver"
                    value={other?.entry_id ?? ""}
                    onChange={setCompareId}
                    options={drivers
                      .filter((driver) => driver !== focus)
                      .map((driver) => {
                        const entry = workspace.entries.find((item) => item.id === driver.entry_id);
                        return entry ? driverOption(entry) : { value: driver.entry_id, label: name(driver.entry_id) };
                      })}
                  />
                </label>
                {other ? (
                  <div className="insight-table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Metric</th>
                          <th>{name(focus.entry_id)}</th>
                          <th>{name(other.entry_id)}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {metrics.map((id) => (
                          <tr key={id}>
                            <th>
                              {definitions[id]?.label ??
                                id.replaceAll("_", " ")}
                            </th>
                            <td
                              title={
                                focus.metrics[id]?.status === "available"
                                  ? (focus.metrics[id].reason ?? undefined)
                                  : explainUnavailable(
                                      focus.metrics[id],
                                      definitions[id],
                                    )
                              }
                            >
                              {formatEstimate(focus.metrics[id])}
                              {focus.metrics[id]?.status !== "available" ? (
                                <small className="insight-unavailable">
                                  {explainUnavailable(
                                    focus.metrics[id],
                                    definitions[id],
                                  )}
                                </small>
                              ) : null}
                            </td>
                            <td
                              title={
                                other.metrics[id]?.status === "available"
                                  ? (other.metrics[id].reason ?? undefined)
                                  : explainUnavailable(
                                      other.metrics[id],
                                      definitions[id],
                                    )
                              }
                            >
                              {formatEstimate(other.metrics[id])}
                              {other.metrics[id]?.status !== "available" ? (
                                <small className="insight-unavailable">
                                  {explainUnavailable(
                                    other.metrics[id],
                                    definitions[id],
                                  )}
                                </small>
                              ) : null}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="insight-empty">
                    Select at least two drivers in the workspace to compare
                    them.
                  </p>
                )}
              </>
            ) : showMetricDisclosure ? (
              <>
                {panelId === "tyre-workload" ? (
                  <TyreLoadProfile metrics={focus.metrics} />
                ) : panelId === "pace-context" ? (
                  <PaceContextVisual metrics={focus.metrics} />
                ) : <StintPaceVisual driver={focus} />}
                <details className="insight-visual-evidence">
                  <summary>Metrics and evidence</summary>
                  {metricGrid}
                </details>
              </>
            ) : metricGrid}
            {[
              "battle-radar",
              "closing-gaps",
              "overtake-opportunities",
            ].includes(panelId) ? (
              <div className="insight-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Following</th>
                      <th>Ahead</th>
                      <th>Gap</th>
                      <th>Closing</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pairs.map((pair) => (
                      <tr key={pair.follower_id}>
                        <th>{name(pair.follower_id)}</th>
                        <td>{name(pair.ahead_id)}</td>
                        <td>
                          {pair.gap_s == null
                            ? "Unavailable"
                            : `${pair.gap_s.toFixed(2)} s`}
                        </td>
                        <td>
                          {pair.closing_rate == null
                            ? "Unavailable"
                            : `${pair.closing_rate.toFixed(3)} s/s`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!pairs.length ? (
                  <p className="insight-empty">
                    No fresh adjacent-car timing reports at this cutoff.
                  </p>
                ) : null}
              </div>
            ) : null}
            {[
              "wake-exposure",
              "closing-gaps",
              "tyre-workload",
              "driver-overview",
            ].includes(panelId) ? (
              <Sparkline
                driver={focus}
                field={
                  panelId === "wake-exposure"
                    ? "wake_scenario_pct"
                    : panelId === "closing-gaps"
                      ? "gap_s"
                      : panelId === "tyre-workload"
                        ? "tyre_load_index"
                        : "speed_kph"
                }
                label={
                  panelId === "wake-exposure"
                    ? "Wake-loss scenario (%)"
                    : panelId === "closing-gaps"
                      ? "Gap to car ahead (s)"
                      : panelId === "tyre-workload"
                        ? "Tyre thermal-load index"
                        : "Ground speed (kph)"
                }
              />
            ) : null}
            {panelId === "braking-analysis" ? (
              <div className="insight-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Onset</th>
                      <th>Entry / exit</th>
                      <th>Duration</th>
                      <th>Peak decel</th>
                    </tr>
                  </thead>
                  <tbody>
                    {focus.braking_zones
                      .slice(-8)
                      .reverse()
                      .map((zone) => (
                        <tr key={zone.start_ms}>
                          <th>{timeLabel(zone.start_ms)}</th>
                          <td>
                            {zone.entry_speed_kph.toFixed(0)} /{" "}
                            {zone.exit_speed_kph.toFixed(0)} kph
                          </td>
                          <td>{zone.duration_s.toFixed(1)} s</td>
                          <td>{zone.peak_deceleration_g.toFixed(2)} g</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
                {!focus.braking_zones.length ? (
                  <p>No supported braking episodes.</p>
                ) : null}
              </div>
            ) : null}
            {panelId === "incident-watch" ? (
              <>
                <p className="insight-notice">
                  Vehicle speed and binary brake data cannot confirm a lockup,
                  collision or off-track location.
                </p>
                <EventList
                  events={incidentEvents.slice(0, Math.min(5, capacity))}
                  name={name}
                />
                {!incidentEvents.length ? (
                  <p>No matching incident candidates or official warnings.</p>
                ) : null}
              </>
            ) : null}
            {panelId === "track-conditions" ? (
              <p className="insight-notice">
                Weather report age:{" "}
                {data.conditions.weather_age_s == null
                  ? "unknown"
                  : `${Number(data.conditions.weather_age_s).toFixed(0)} s`}
                .{" "}
                {data.conditions.rain_reported
                  ? "Rain reported. Dry-grip scenarios need caution."
                  : "No fresh rain report indicating rainfall."}{" "}
                Wind direction is unresolved without a calibrated north axis and
                source convention.
              </p>
            ) : null}
            {panelId === "pit-scenarios" ? (
              <p className="insight-notice">
                Base net loss assumption:{" "}
                {String(data.assumptions.pit_loss_scenario_s)} s; fresh-tyre
                gain: {String(data.assumptions.fresh_tyre_gain_scenario_s)}{" "}
                s/lap. These scenarios do not recommend an optimal stop or
                guarantee a pit-exit position.
              </p>
            ) : null}
            {panelId === "model-quality" ? (
              <>
                <details>
                  <summary>Assumptions · {data.version}</summary>
                  <dl className="insight-evidence">
                    {Object.entries(data.assumptions).map(([key, value]) => (
                      <div key={key}>
                        <dt>{key.replaceAll("_", " ")}</dt>
                        <dd>
                          {value == null ? "Not calibrated" : String(value)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </details>
                <details>
                  <summary>Model limitations</summary>
                  <ul>
                    {data.warnings.map((warning, index) => (
                      <li key={index}>{warning}</li>
                    ))}
                  </ul>
                </details>
              </>
            ) : null}
          </>
        ) : null}
        {data && panelId !== "model-quality" && !reportsOnly ? (
          <small className="insight-footer">
            Estimation model · expand values for evidence and assumptions.
          </small>
        ) : null}
      </div>
    </WidgetCard>
  );
}
