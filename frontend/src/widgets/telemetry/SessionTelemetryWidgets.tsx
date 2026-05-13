import { WidgetCard } from "../shared/WidgetCard";
import { WidgetEmpty, WidgetError, WidgetLoading } from "../shared/WidgetState";
import {
  useWorkspaceEntryLapsResource,
  useWorkspaceCarTelemetryResource,
  useWorkspacePositionTelemetryResource,
} from "../../features/sessions/session-data.hooks";
import { useSessionWorkspace } from "../../features/sessions/SessionWorkspaceContext";
import {
  buildBrakePoints,
  buildLapTrendPoints,
  buildLinePath,
  buildReplayTrackViewBox,
  buildTrackPoints,
  downsamplePoints,
  formatLapTime,
  getEntryAccent,
  getEntryDisplayName,
} from "../../features/sessions/session-utils";

type WidgetOptions = {
  title?: string;
  metric?: "speed_kph" | "throttle_pct";
  metricLabel?: string;
  unit?: string;
  requiresLap?: boolean;
  scope?: "lap" | "session";
};

type LineSeries = {
  key: string;
  label: string;
  color: string;
  points: Array<{ x: number; y: number }>;
};

export function TelemetryLineChartWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  const widgetOptions = (options ?? {}) as WidgetOptions;
  const workspace = useSessionWorkspace();
  const requiresLap = widgetOptions.requiresLap === true;
  const canRequestTelemetry = workspace.selectedEntries.length > 0 && (!requiresLap || workspace.lapSelection !== "all");
  const telemetry = useWorkspaceCarTelemetryResource({
    entryMode: "selected",
    scope: "auto",
    requireLap: requiresLap,
    limit: 5000,
    enabled: canRequestTelemetry,
  });

  if (workspace.selectedEntries.length === 0) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Telemetry"}>
        <WidgetEmpty message="Choose at least one driver to unlock telemetry widgets." />
      </WidgetCard>
    );
  }

  if (requiresLap && workspace.lapSelection === "all") {
    return (
      <WidgetCard title={widgetOptions.title ?? "Telemetry"}>
        <WidgetEmpty message="Choose a specific lap to render lap-scoped telemetry." />
      </WidgetCard>
    );
  }

  if (telemetry.isError) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Telemetry"}>
        <WidgetError />
      </WidgetCard>
    );
  }

  if (!telemetry.ready) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Telemetry"}>
        <WidgetEmpty message={telemetry.waitMessage} />
      </WidgetCard>
    );
  }

  if (telemetry.isLoading) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Telemetry"}>
        <WidgetLoading />
      </WidgetCard>
    );
  }

  if (telemetry.isError) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Telemetry"}>
        <WidgetError />
      </WidgetCard>
    );
  }

  const metric = widgetOptions.metric ?? "speed_kph";
  const series: LineSeries[] = workspace.selectedEntries.map((entry, index) => ({
    key: entry.id,
    label: getEntryDisplayName(entry),
    color: getEntryAccent(entry, index),
    points: downsamplePoints(
      (telemetry.dataByEntryId[entry.id] ?? [])
        .filter((sample) => sample[metric] != null)
        .map((sample) => ({
          x: sample.session_time_ms,
          y: Number(sample[metric]),
        })),
    ),
  }));

  return (
    <WidgetCard
      title={widgetOptions.title ?? "Telemetry"}
      description={`${widgetOptions.metricLabel ?? "Telemetry"} trace${widgetOptions.unit ? ` · ${widgetOptions.unit}` : ""}`}
    >
      <SimpleLineChart series={series} emptyMessage="Telemetry samples were not available for the selected drivers." />
    </WidgetCard>
  );
}

export function BrakeTraceChartWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  const widgetOptions = (options ?? {}) as WidgetOptions;
  const workspace = useSessionWorkspace();
  const requiresLap = widgetOptions.requiresLap !== false;
  const canRequestTelemetry = workspace.selectedEntries.length > 0 && (!requiresLap || workspace.lapSelection !== "all");
  const telemetry = useWorkspaceCarTelemetryResource({
    entryMode: "selected",
    scope: "auto",
    requireLap: requiresLap,
    limit: 5000,
    enabled: canRequestTelemetry,
  });

  if (workspace.selectedEntries.length === 0) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Brake Trace"}>
        <WidgetEmpty message="Choose at least one driver to compare brake traces." />
      </WidgetCard>
    );
  }

  if (requiresLap && workspace.lapSelection === "all") {
    return (
      <WidgetCard title={widgetOptions.title ?? "Brake Trace"}>
        <WidgetEmpty message="Choose a specific lap to compare braking points." />
      </WidgetCard>
    );
  }

  if (telemetry.isError) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Brake Trace"}>
        <WidgetError />
      </WidgetCard>
    );
  }

  if (!telemetry.ready) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Brake Trace"}>
        <WidgetEmpty message={telemetry.waitMessage} />
      </WidgetCard>
    );
  }

  if (telemetry.isLoading) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Brake Trace"}>
        <WidgetLoading />
      </WidgetCard>
    );
  }

  if (telemetry.isError) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Brake Trace"}>
        <WidgetError />
      </WidgetCard>
    );
  }

  const series: LineSeries[] = workspace.selectedEntries.map((entry, index) => ({
    key: entry.id,
    label: getEntryDisplayName(entry),
    color: getEntryAccent(entry, index),
    points: downsamplePoints(buildBrakePoints(telemetry.dataByEntryId[entry.id] ?? [])),
  }));

  return (
    <WidgetCard
      title={widgetOptions.title ?? "Brake Trace"}
      description="Binary brake-on trace across the selected lap."
    >
      <SimpleLineChart series={series} emptyMessage="Brake telemetry was not available for the selected drivers." />
    </WidgetCard>
  );
}

export function LapTimeTrendWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  const widgetOptions = (options ?? {}) as WidgetOptions;
  const workspace = useSessionWorkspace();
  const laps = useWorkspaceEntryLapsResource({
    entryMode: "selected",
    enabled: workspace.selectedEntries.length > 0,
  });

  if (workspace.selectedEntries.length === 0) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Lap Time Trend"}>
        <WidgetEmpty message="Choose drivers to compare lap-time evolution." />
      </WidgetCard>
    );
  }

  if (laps.isLoading) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Lap Time Trend"}>
        <WidgetLoading />
      </WidgetCard>
    );
  }

  if (laps.isError) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Lap Time Trend"}>
        <WidgetError />
      </WidgetCard>
    );
  }

  const series: LineSeries[] = workspace.selectedEntries.map((entry, index) => ({
    key: entry.id,
    label: getEntryDisplayName(entry),
    color: getEntryAccent(entry, index),
    points: buildLapTrendPoints(laps.dataByEntryId[entry.id] ?? []),
  }));

  return (
    <WidgetCard
      title={widgetOptions.title ?? "Lap Time Trend"}
      description="Full-session lap progression for the selected drivers."
    >
      <SimpleLineChart series={series} emptyMessage="Lap-time data was not available for the selected drivers." />
    </WidgetCard>
  );
}

export function LapTableWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  const widgetOptions = (options ?? {}) as WidgetOptions;
  const workspace = useSessionWorkspace();
  const laps = useWorkspaceEntryLapsResource({
    entryMode: "selected",
    enabled: workspace.selectedEntries.length > 0,
  });

  if (workspace.selectedEntries.length === 0) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Lap Table"}>
        <WidgetEmpty message="Choose drivers to inspect lap-by-lap data." />
      </WidgetCard>
    );
  }

  if (laps.isLoading) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Lap Table"}>
        <WidgetLoading />
      </WidgetCard>
    );
  }

  if (laps.isError) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Lap Table"}>
        <WidgetError />
      </WidgetCard>
    );
  }

  const rows = workspace.selectedEntries
    .flatMap((entry, index) =>
      (laps.dataByEntryId[entry.id] ?? [])
        .filter((lap) => workspace.lapSelection === "all" || lap.lap_number === workspace.lapSelection)
        .map((lap) => ({
          id: `${entry.id}-${lap.id}`,
          driver: getEntryDisplayName(entry),
          accent: getEntryAccent(entry, index),
          lap,
        })),
    )
    .sort((left, right) => right.lap.lap_number - left.lap.lap_number)
    .slice(0, workspace.lapSelection === "all" ? 24 : 12);

  return (
    <WidgetCard
      title={widgetOptions.title ?? "Lap Table"}
      description="Selected-driver lap data for the current workspace filters."
    >
      {rows.length === 0 ? (
        <WidgetEmpty message="No laps matched the current driver and lap selection." />
      ) : (
        <div className="telemetry-table">
          <div className="telemetry-table__header telemetry-table__row">
            <span>Driver</span>
            <span>Lap</span>
            <span>Time</span>
            <span>Compound</span>
            <span>Tyre Life</span>
          </div>
          {rows.map((row) => (
            <div key={row.id} className="telemetry-table__row">
              <span className="telemetry-driver-chip">
                <i style={{ backgroundColor: row.accent }} />
                {row.driver}
              </span>
              <span>L{row.lap.lap_number}</span>
              <span>{formatLapTime(row.lap.lap_time_ms)}</span>
              <span>{row.lap.compound ?? "N/A"}</span>
              <span>{row.lap.tyre_life ?? "N/A"}</span>
            </div>
          ))}
        </div>
      )}
    </WidgetCard>
  );
}

export function SessionTrackMapWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  const widgetOptions = (options ?? {}) as WidgetOptions;
  const workspace = useSessionWorkspace();
  const isLapScoped = widgetOptions.scope === "lap";
  const canRequestTelemetry = workspace.selectedEntries.length > 0 && (!isLapScoped || workspace.lapSelection !== "all");
  const positions = useWorkspacePositionTelemetryResource({
    entryMode: "selected",
    scope: isLapScoped ? "lap" : "session",
    requireLap: isLapScoped,
    limit: isLapScoped ? 5000 : 20000,
    enabled: canRequestTelemetry,
  });

  if (workspace.selectedEntries.length === 0) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Track Map"}>
        <WidgetEmpty message="Choose drivers to draw their track map overlays." />
      </WidgetCard>
    );
  }

  if (isLapScoped && workspace.lapSelection === "all") {
    return (
      <WidgetCard title={widgetOptions.title ?? "Track Map"}>
        <WidgetEmpty message="Choose a specific lap to render a lap-scoped track map." />
      </WidgetCard>
    );
  }

  if (positions.isError) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Track Map"}>
        <WidgetError />
      </WidgetCard>
    );
  }

  if (!positions.ready) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Track Map"}>
        <WidgetEmpty message={positions.waitMessage} />
      </WidgetCard>
    );
  }

  if (positions.isLoading) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Track Map"}>
        <WidgetLoading />
      </WidgetCard>
    );
  }

  if (positions.isError) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Track Map"}>
        <WidgetError />
      </WidgetCard>
    );
  }

  const traces = workspace.selectedEntries.map((entry, index) => ({
    key: entry.id,
    label: getEntryDisplayName(entry),
    color: getEntryAccent(entry, index),
    points: downsamplePoints(buildTrackPoints(positions.dataByEntryId[entry.id] ?? []), 220),
  }));
  const allPoints = traces.flatMap((trace) => trace.points);

  return (
    <WidgetCard
      title={widgetOptions.title ?? "Track Map"}
      description="Selected-driver position overlays for the current session scope."
    >
      {allPoints.length === 0 ? (
        <WidgetEmpty message="Track position data was not available for the selected drivers." />
      ) : (
        <TrackMap traces={traces} />
      )}
    </WidgetCard>
  );
}

function SimpleLineChart({
  series,
  emptyMessage,
}: {
  series: LineSeries[];
  emptyMessage: string;
}) {
  const activeSeries = series.filter((item) => item.points.length > 0);

  if (activeSeries.length === 0) {
    return <WidgetEmpty message={emptyMessage} />;
  }

  return (
    <div className="telemetry-chart">
      <div className="telemetry-chart__legend">
        {activeSeries.map((item) => (
          <span key={item.key} className="telemetry-driver-chip">
            <i style={{ backgroundColor: item.color }} />
            {item.label}
          </span>
        ))}
      </div>

      <svg viewBox="0 0 720 280" className="telemetry-chart__svg" preserveAspectRatio="none">
        <rect x="0" y="0" width="720" height="280" rx="18" className="telemetry-chart__bg" />
        {[48, 96, 144, 192, 240].map((y) => (
          <line key={y} x1="16" y1={y} x2="704" y2={y} className="telemetry-chart__grid" />
        ))}
        {activeSeries.map((item) => (
          <path
            key={item.key}
            d={buildLinePath(item.points, 720, 280)}
            fill="none"
            stroke={item.color}
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}
      </svg>
    </div>
  );
}

function TrackMap({
  traces,
}: {
  traces: LineSeries[];
}) {
  const points = traces.flatMap((trace) => trace.points);
  const viewBox = buildReplayTrackViewBox(points);

  return (
    <div className="telemetry-chart telemetry-chart--track">
      <div className="telemetry-chart__legend">
        {traces.map((item) => (
          <span key={item.key} className="telemetry-driver-chip">
            <i style={{ backgroundColor: item.color }} />
            {item.label}
          </span>
        ))}
      </div>
      <svg viewBox={viewBox} className="telemetry-track-map">
        {traces.map((trace) => (
          <path
            key={trace.key}
            d={trace.points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ")}
            fill="none"
            stroke={trace.color}
            strokeWidth="10"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity="0.9"
          />
        ))}
      </svg>
    </div>
  );
}
