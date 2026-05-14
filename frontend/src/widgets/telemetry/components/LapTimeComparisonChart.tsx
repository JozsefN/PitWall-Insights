import { useState } from "react";
import { formatLapTime } from "../../../features/sessions/session-utils";
import { WidgetEmpty } from "../../shared/WidgetState";
import type {
  LapChartSeries,
  LapReferenceSeries,
  PlottedLapPoint,
  TrackStatusBand,
} from "../models";
import {
  formatTrackStatusDuration,
  formatTrackStatusRange,
  getTrackStatusLabel,
} from "../utils/track-status";
import { TrackStatusSummary } from "./TrackStatusSummary";

type LapTimeComparisonChartProps = {
  series: LapChartSeries[];
  referenceSeries: LapReferenceSeries | null;
  statusBands: TrackStatusBand[];
  emptyMessage: string;
};

export function LapTimeComparisonChart({
  series,
  referenceSeries,
  statusBands,
  emptyMessage,
}: LapTimeComparisonChartProps) {
  const [hoveredPoint, setHoveredPoint] = useState<PlottedLapPoint | null>(null);
  const activeSeries = series.filter((item) => item.points.length > 0);

  if (activeSeries.length === 0) {
    return <WidgetEmpty message={emptyMessage} />;
  }

  const width = 860;
  const height = 380;
  const plot = {
    left: 76,
    right: 24,
    top: 26,
    bottom: 46,
  };
  const allLapNumbers = [
    ...activeSeries.flatMap((item) => item.points.map((point) => point.lapNumber)),
    ...(referenceSeries?.points.map((point) => point.lapNumber) ?? []),
    ...statusBands.flatMap((band) => [band.startLapValue, band.endLapValue]),
  ];
  const allValues = [
    ...activeSeries.flatMap((item) => item.points.map((point) => point.chartValueMs)),
    ...(referenceSeries?.points.map((point) => point.valueMs) ?? []),
  ];
  const minLap = Math.min(...allLapNumbers);
  const maxLap = Math.max(...allLapNumbers);
  const minValue = Math.min(...allValues);
  const maxValue = Math.max(...allValues);
  const valuePadding = Math.max((maxValue - minValue) * 0.1, 750);
  const yDomainMin = minValue - valuePadding;
  const yDomainMax = maxValue + valuePadding;
  const referenceByLap = new Map(referenceSeries?.points.map((point) => [point.lapNumber, point.valueMs]) ?? []);
  const scaleX = (lapNumber: number) => scaleNumber(lapNumber, minLap, maxLap, plot.left, width - plot.right);
  const scaleY = (valueMs: number) => scaleNumber(valueMs, yDomainMin, yDomainMax, height - plot.bottom, plot.top);
  const yTicks = buildTimeTicks(yDomainMin, yDomainMax, 6);
  const xTicks = buildLapTicks(minLap, maxLap, 8);
  const plottedSeries = activeSeries.map((item) => ({
    ...item,
    points: item.points.map((point) => {
      const referenceValueMs = referenceByLap.get(point.lapNumber) ?? null;
      return {
        ...point,
        plotX: scaleX(point.lapNumber),
        plotY: scaleY(point.chartValueMs),
        referenceValueMs,
        deltaToReferenceMs: referenceValueMs == null ? null : point.lapTimeMs - referenceValueMs,
      };
    }),
  }));
  const plottedReference = referenceSeries
    ? {
        ...referenceSeries,
        points: referenceSeries.points.map((point) => ({
          ...point,
          plotX: scaleX(point.lapNumber),
          plotY: scaleY(point.valueMs),
        })),
      }
    : null;

  return (
    <div className="lap-pace-chart">
      <div className="lap-pace-chart__legend">
        {activeSeries.map((item) => (
          <span key={item.key} className="telemetry-driver-chip">
            <i style={{ backgroundColor: item.color }} />
            {item.label}
          </span>
        ))}
        {referenceSeries ? (
          <span className="telemetry-driver-chip telemetry-driver-chip--reference">
            <i style={{ backgroundColor: referenceSeries.color }} />
            {referenceSeries.label}
          </span>
        ) : null}
      </div>
      <TrackStatusSummary bands={statusBands} />

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="lap-pace-chart__svg"
        role="img"
        aria-label="Lap time comparison chart"
        onMouseLeave={() => setHoveredPoint(null)}
      >
        <rect x="0" y="0" width={width} height={height} rx="12" className="lap-pace-chart__bg" />

        {statusBands.map((band) => {
          const x1 = Math.max(plot.left, scaleX(band.startLapValue));
          const x2 = Math.min(width - plot.right, scaleX(band.endLapValue));
          const bandWidth = Math.max(x2 - x1, 3);
          return (
            <g key={band.key}>
              <rect
                x={x1}
                y={plot.top}
                width={bandWidth}
                height={height - plot.top - plot.bottom}
                className={`lap-pace-chart__status-band lap-pace-chart__status-band--${band.kind}`}
              >
                <title>{`${band.label} ${formatTrackStatusRange(band)} - ${formatTrackStatusDuration(band.durationMs)}`}</title>
              </rect>
              {bandWidth > 82 ? (
                <text
                  x={x1 + 8}
                  y={plot.top + 16}
                  className="lap-pace-chart__status-label"
                >
                  {`${band.label} ${formatTrackStatusDuration(band.durationMs)}`}
                </text>
              ) : null}
            </g>
          );
        })}

        {yTicks.map((tick) => {
          const y = scaleY(tick);
          return (
            <g key={tick}>
              <line x1={plot.left} y1={y} x2={width - plot.right} y2={y} className="lap-pace-chart__grid" />
              <text x={plot.left - 12} y={y + 4} className="lap-pace-chart__axis-label" textAnchor="end">
                {formatLapAxisTime(tick)}
              </text>
            </g>
          );
        })}

        {xTicks.map((tick) => {
          const x = scaleX(tick);
          return (
            <g key={tick}>
              <line x1={x} y1={plot.top} x2={x} y2={height - plot.bottom} className="lap-pace-chart__grid" />
              <text x={x} y={height - 18} className="lap-pace-chart__axis-label" textAnchor="middle">
                {tick}
              </text>
            </g>
          );
        })}

        <text
          x={plot.left + (width - plot.left - plot.right) / 2}
          y={height - 4}
          className="lap-pace-chart__axis-title"
          textAnchor="middle"
        >
          Lap
        </text>
        <text
          x="20"
          y={plot.top + (height - plot.top - plot.bottom) / 2}
          className="lap-pace-chart__axis-title"
          textAnchor="middle"
          transform={`rotate(-90 20 ${plot.top + (height - plot.top - plot.bottom) / 2})`}
        >
          Lap time
        </text>

        {plottedReference ? (
          <path
            d={buildPlotPath(plottedReference.points)}
            fill="none"
            stroke={plottedReference.color}
            className="lap-pace-chart__reference-line"
          />
        ) : null}

        {plottedSeries.map((item) =>
          splitLapSegments(item.points).map((segment, segmentIndex) => (
            <path
              key={`${item.key}-${segmentIndex}`}
              d={buildPlotPath(segment)}
              fill="none"
              stroke={item.color}
              className="lap-pace-chart__line"
            />
          )),
        )}

        {plottedSeries.flatMap((item) =>
          item.points.map((point) => (
            <circle
              key={`${item.key}-${point.lapNumber}`}
              cx={point.plotX}
              cy={point.plotY}
              r={point.isOutlier || point.isPitLap || point.statusKind !== "green" ? 4.6 : 3.6}
              fill={point.color}
              className={`lap-pace-chart__point lap-pace-chart__point--${point.statusKind}`}
              tabIndex={0}
              onMouseEnter={() => setHoveredPoint(point)}
              onFocus={() => setHoveredPoint(point)}
              onBlur={() => setHoveredPoint(null)}
            >
              <title>{`${point.label} lap ${point.lapNumber}: ${formatLapTime(point.lapTimeMs)}`}</title>
            </circle>
          )),
        )}

        {hoveredPoint ? <LapPointTooltip point={hoveredPoint} width={width} plot={plot} /> : null}
      </svg>
    </div>
  );
}

function LapPointTooltip({
  point,
  width,
  plot,
}: {
  point: PlottedLapPoint;
  width: number;
  plot: { left: number; right: number; top: number; bottom: number };
}) {
  const tooltipWidth = 220;
  const tooltipHeight = 118;
  const x = point.plotX + tooltipWidth + 18 > width - plot.right ? point.plotX - tooltipWidth - 14 : point.plotX + 14;
  const y = Math.max(plot.top + 8, point.plotY - tooltipHeight - 12);
  const status = getTrackStatusLabel(point.trackStatus);

  return (
    <g className="lap-pace-tooltip" transform={`translate(${x} ${y})`}>
      <rect width={tooltipWidth} height={tooltipHeight} rx="10" className="lap-pace-tooltip__bg" />
      <circle cx="16" cy="18" r="5" fill={point.color} />
      <text x="28" y="22" className="lap-pace-tooltip__title">
        {point.label}
      </text>
      <text x="14" y="46" className="lap-pace-tooltip__line">
        {`Lap ${point.lapNumber} - ${formatLapTime(point.lapTimeMs)}`}
      </text>
      <text x="14" y="66" className="lap-pace-tooltip__line">
        {`Delta ${point.deltaToReferenceMs == null ? "N/A" : formatSignedDelta(point.deltaToReferenceMs)}`}
      </text>
      <text x="14" y="86" className="lap-pace-tooltip__line">
        {`Tyre ${point.compound ?? "N/A"}${point.tyreLife == null ? "" : ` L${point.tyreLife}`}`}
      </text>
      <text x="14" y="106" className="lap-pace-tooltip__muted">
        {`${status}${point.lapPosition == null ? "" : ` - P${point.lapPosition}`}`}
      </text>
    </g>
  );
}

function buildPlotPath(points: Array<{ plotX: number; plotY: number }>) {
  return points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.plotX.toFixed(2)} ${point.plotY.toFixed(2)}`)
    .join(" ");
}

function splitLapSegments(points: PlottedLapPoint[]) {
  const segments: PlottedLapPoint[][] = [];
  let current: PlottedLapPoint[] = [];

  for (const point of points) {
    const previous = current[current.length - 1];
    if (previous && point.lapNumber - previous.lapNumber > 1) {
      segments.push(current);
      current = [];
    }
    current.push(point);
  }

  if (current.length > 0) {
    segments.push(current);
  }

  return segments.filter((segment) => segment.length > 1);
}

function buildTimeTicks(minValue: number, maxValue: number, count: number) {
  if (minValue === maxValue) {
    return [minValue];
  }

  const step = (maxValue - minValue) / Math.max(count - 1, 1);
  return Array.from({ length: count }, (_, index) => minValue + step * index);
}

function buildLapTicks(minLap: number, maxLap: number, maxCount: number) {
  if (minLap === maxLap) {
    return [minLap];
  }

  const span = maxLap - minLap;
  const step = Math.max(1, Math.ceil(span / Math.max(maxCount - 1, 1)));
  const ticks: number[] = [];
  for (let lap = minLap; lap <= maxLap; lap += step) {
    ticks.push(lap);
  }
  if (ticks[ticks.length - 1] !== maxLap) {
    ticks.push(maxLap);
  }
  return ticks;
}

function formatLapAxisTime(totalMs: number) {
  const safe = Math.max(0, Math.floor(totalMs));
  const minutes = Math.floor(safe / 60000);
  const seconds = Math.floor((safe % 60000) / 1000);
  const tenths = Math.floor((safe % 1000) / 100);
  return `${minutes}:${String(seconds).padStart(2, "0")}.${tenths}`;
}

function formatSignedDelta(deltaMs: number) {
  const sign = deltaMs >= 0 ? "+" : "-";
  return `${sign}${(Math.abs(deltaMs) / 1000).toFixed(3)}s`;
}

function scaleNumber(
  value: number,
  domainMin: number,
  domainMax: number,
  rangeMin: number,
  rangeMax: number,
) {
  if (domainMin === domainMax) {
    return (rangeMin + rangeMax) / 2;
  }

  const progress = (value - domainMin) / (domainMax - domainMin);
  return rangeMin + progress * (rangeMax - rangeMin);
}
