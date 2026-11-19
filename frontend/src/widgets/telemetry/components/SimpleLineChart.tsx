import { useState } from "react";
import { buildLinePath } from "../../../features/sessions/session-utils";
import { WidgetEmpty } from "../../shared/WidgetState";
import { useTelemetryPlotSize } from "../../shared/widget-size";
import type { LineSeries } from "../models";
import { ChartDriverPicker } from "./ChartDriverPicker";

type SimpleLineChartProps = {
  series: LineSeries[];
  emptyMessage: string;
  alignByLap?: boolean;
  valueRange?: [number, number];
};

export function SimpleLineChart({
  series,
  emptyMessage,
  alignByLap,
  valueRange,
}: SimpleLineChartProps) {
  const [driverFocus, setDriverFocus] = useState("");
  const { width, height } = useTelemetryPlotSize();
  const activeSeries = series.filter((item) => item.points.length > 0);

  if (activeSeries.length === 0) {
    return <WidgetEmpty message={emptyMessage} />;
  }

  const focusedId = series.some((item) => item.key === driverFocus)
    ? driverFocus
    : "";
  const alignedSeries = alignByLap
    ? activeSeries.map((item) => ({
        ...item,
        points: item.points.map((point) => ({
          x: point.x - item.points[0].x,
          y: point.y,
        })),
      }))
    : activeSeries;
  const chartSeries = focusedId
    ? alignedSeries.filter((item) => item.key === focusedId)
    : alignedSeries;
  const points = alignedSeries.flatMap((item) => item.points);
  const domain = {
    minX: Math.min(...points.map((point) => point.x)),
    maxX: Math.max(...points.map((point) => point.x)),
    minY: valueRange?.[0] ?? Math.min(...points.map((point) => point.y)),
    maxY: valueRange?.[1] ?? Math.max(...points.map((point) => point.y)),
  };
  const dense = chartSeries.length > 8;

  return (
    <div className="telemetry-chart" data-dense={dense}>
      <ChartDriverPicker
        drivers={series.map((item) => ({
          entry: item.entry,
          id: item.key,
          label: item.label,
        }))}
        value={focusedId}
        onChange={setDriverFocus}
      />
      {activeSeries.length < series.length ? (
        <p className="telemetry-chart__coverage">
          Samples available for {activeSeries.length} of {series.length}{" "}
          drivers.
        </p>
      ) : null}
      {chartSeries.length === 0 ? (
        <WidgetEmpty message="No telemetry samples for this driver in the current view." />
      ) : (
        <>
          <div
            className="telemetry-chart__legend comparison-legend"
            tabIndex={dense ? 0 : undefined}
            aria-label="Plotted drivers"
          >
            {chartSeries.map((item) => (
              <span key={item.key} className="telemetry-driver-chip">
                <i style={{ backgroundColor: item.color }} />
                {item.label}
              </span>
            ))}
          </div>

          <svg
            viewBox={`0 0 ${width} ${height}`}
            style={{ height }}
            className="telemetry-chart__svg"
            preserveAspectRatio="none"
            role="img"
            aria-label={
              alignByLap
                ? "Telemetry comparison by elapsed lap time"
                : "Telemetry comparison by session time"
            }
          >
            <rect
              width={width}
              height={height}
              rx="12"
              className="telemetry-chart__bg"
            />
            {[1, 2, 3, 4, 5].map((step) => (
              <line
                key={step}
                x1="12"
                y1={(step * height) / 6}
                x2={width - 12}
                y2={(step * height) / 6}
                className="telemetry-chart__grid"
              />
            ))}
            {chartSeries.map((item) => (
              <path
                key={item.key}
                d={buildLinePath(item.points, width, height, domain)}
                fill="none"
                stroke={item.color}
                strokeWidth={dense ? 1.4 : 2.5}
                data-entry-id={item.key}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            ))}
          </svg>
        </>
      )}
    </div>
  );
}
