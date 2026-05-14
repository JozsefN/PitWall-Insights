import { useState } from "react";
import { formatLapTime } from "../../../features/sessions/session-utils";
import { WidgetEmpty } from "../../shared/WidgetState";
import type {
  PlottedStintPoint,
  StintSeries,
  TrackStatusBand,
} from "../models";
import {
  formatTrackStatusDuration,
  formatTrackStatusRange,
} from "../utils/track-status";
import {
  getCompoundColor,
  getCompoundLabel,
  getCompoundShortLabel,
  getStintStatusLabel,
} from "../utils/stint-analysis";
import { TrackStatusSummary } from "./TrackStatusSummary";

type StintAnalysisChartProps = {
  series: StintSeries[];
  statusBands: TrackStatusBand[];
  hiddenStintKeys: Set<string>;
  showTrend: boolean;
  emptyMessage: string;
};

export function StintAnalysisChart({
  series,
  statusBands,
  hiddenStintKeys,
  showTrend,
  emptyMessage,
}: StintAnalysisChartProps) {
  const [hoveredPoint, setHoveredPoint] = useState<PlottedStintPoint | null>(null);
  const activeSeries = series.filter((item) => !hiddenStintKeys.has(item.key) && item.points.length > 0);

  if (activeSeries.length === 0) {
    return <WidgetEmpty message={emptyMessage} />;
  }

  const width = 900;
  const height = 380;
  const plot = {
    left: 76,
    right: 28,
    top: 28,
    bottom: 48,
  };
  const allLapNumbers = activeSeries.flatMap((item) => item.points.map((point) => point.lapNumber));
  const allBandLapValues = statusBands.flatMap((band) => [band.startLapValue, band.endLapValue]);
  const allValues = activeSeries.flatMap((item) => item.points.map((point) => point.lapTimeMs));
  const minLap = Math.min(...allLapNumbers, ...allBandLapValues);
  const maxLap = Math.max(...allLapNumbers, ...allBandLapValues);
  const minValue = Math.min(...allValues);
  const maxValue = Math.max(...allValues);
  const valuePadding = Math.max((maxValue - minValue) * 0.1, 700);
  const yDomainMin = minValue - valuePadding;
  const yDomainMax = maxValue + valuePadding;
  const scaleX = (lapNumber: number) => scaleNumber(lapNumber, minLap, maxLap, plot.left, width - plot.right);
  const scaleY = (valueMs: number) => scaleNumber(valueMs, yDomainMin, yDomainMax, height - plot.bottom, plot.top);
  const yTicks = buildTimeTicks(yDomainMin, yDomainMax, 6);
  const xTicks = buildLapTicks(minLap, maxLap, 9);
  const plottedSeries = activeSeries.map((item) => ({
    ...item,
    points: item.points.map((point) => ({
      ...point,
      plotX: scaleX(point.lapNumber),
      plotY: scaleY(point.lapTimeMs),
    })),
  }));

  return (
    <div className="stint-chart">
      <div className="stint-chart__legend">
        {activeSeries.map((item) => (
          <span key={item.key} className="stint-chip">
            <i style={{ backgroundColor: item.driverColor }} />
            <b style={{ backgroundColor: getCompoundColor(item.compound) }} />
            {`${item.driverLabel} S${item.stintNumber}`}
          </span>
        ))}
      </div>
      <TrackStatusSummary bands={statusBands} />

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="stint-chart__svg"
        role="img"
        aria-label="Stint analysis chart"
        onMouseLeave={() => setHoveredPoint(null)}
      >
        <rect x="0" y="0" width={width} height={height} rx="12" className="stint-chart__bg" />

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
                className={`stint-chart__status-band stint-chart__status-band--${band.kind}`}
              >
                <title>{`${band.label} ${formatTrackStatusRange(band)} - ${formatTrackStatusDuration(band.durationMs)}`}</title>
              </rect>
              {bandWidth > 82 ? (
                <text
                  x={x1 + 8}
                  y={plot.top + 16}
                  className="stint-chart__status-label"
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
              <line x1={plot.left} y1={y} x2={width - plot.right} y2={y} className="stint-chart__grid" />
              <text x={plot.left - 12} y={y + 4} className="stint-chart__axis-label" textAnchor="end">
                {formatLapAxisTime(tick)}
              </text>
            </g>
          );
        })}

        {xTicks.map((tick) => {
          const x = scaleX(tick);
          return (
            <g key={tick}>
              <line x1={x} y1={plot.top} x2={x} y2={height - plot.bottom} className="stint-chart__grid" />
              <text x={x} y={height - 18} className="stint-chart__axis-label" textAnchor="middle">
                {tick}
              </text>
            </g>
          );
        })}

        <text
          x={plot.left + (width - plot.left - plot.right) / 2}
          y={height - 4}
          className="stint-chart__axis-title"
          textAnchor="middle"
        >
          Session lap
        </text>
        <text
          x="20"
          y={plot.top + (height - plot.top - plot.bottom) / 2}
          className="stint-chart__axis-title"
          textAnchor="middle"
          transform={`rotate(-90 20 ${plot.top + (height - plot.top - plot.bottom) / 2})`}
        >
          Lap time
        </text>

        {plottedSeries.map((item) => (
          <path
            key={item.key}
            d={buildPlotPath(item.points)}
            fill="none"
            stroke={item.driverColor}
            className="stint-chart__line"
          />
        ))}

        {showTrend
          ? plottedSeries.map((item) => {
              const trend = buildTrendPath(item, scaleY);
              return trend ? (
                <path
                  key={`${item.key}:trend`}
                  d={trend}
                  fill="none"
                  stroke={getCompoundColor(item.compound)}
                  className="stint-chart__trend"
                />
              ) : null;
            })
          : null}

        {plottedSeries.flatMap((item) =>
          item.points.map((point) => (
            <g key={point.key}>
              <circle
                cx={point.plotX}
                cy={point.plotY}
                r={5}
                fill={getCompoundColor(point.compound)}
                className={`stint-chart__point stint-chart__point--${point.statusKind}`}
                tabIndex={0}
                onMouseEnter={() => setHoveredPoint(point)}
                onFocus={() => setHoveredPoint(point)}
                onBlur={() => setHoveredPoint(null)}
              >
                <title>{`${point.driverLabel} stint ${point.stintNumber} lap ${point.lapNumber}: ${formatLapTime(point.lapTimeMs)}`}</title>
              </circle>
              <circle cx={point.plotX} cy={point.plotY} r={2.2} fill={point.driverColor} className="stint-chart__point-core" />
            </g>
          )),
        )}

        {hoveredPoint ? <StintPointTooltip point={hoveredPoint} width={width} plot={plot} /> : null}
      </svg>
    </div>
  );
}

function StintPointTooltip({
  point,
  width,
  plot,
}: {
  point: PlottedStintPoint;
  width: number;
  plot: { left: number; right: number; top: number; bottom: number };
}) {
  const tooltipWidth = 234;
  const tooltipHeight = 136;
  const x = point.plotX + tooltipWidth + 18 > width - plot.right ? point.plotX - tooltipWidth - 14 : point.plotX + 14;
  const y = Math.max(plot.top + 8, point.plotY - tooltipHeight - 12);
  const delta =
    point.deltaFromFirstMs == null
      ? "N/A"
      : `${point.deltaFromFirstMs >= 0 ? "+" : "-"}${(Math.abs(point.deltaFromFirstMs) / 1000).toFixed(3)}s`;

  return (
    <g className="stint-tooltip" transform={`translate(${x} ${y})`}>
      <rect width={tooltipWidth} height={tooltipHeight} rx="10" className="stint-tooltip__bg" />
      <circle cx="16" cy="18" r="5" fill={point.driverColor} />
      <circle cx="31" cy="18" r="5" fill={getCompoundColor(point.compound)} />
      <text x="44" y="22" className="stint-tooltip__title">
        {point.driverLabel}
      </text>
      <text x="14" y="46" className="stint-tooltip__line">
        {`S${point.stintNumber} ${getCompoundLabel(point.compound)} (${getCompoundShortLabel(point.compound)})`}
      </text>
      <text x="14" y="66" className="stint-tooltip__line">
        {`Lap ${point.lapNumber} - ${formatLapTime(point.lapTimeMs)}`}
      </text>
      <text x="14" y="86" className="stint-tooltip__line">
        {`Stint lap ${point.stintLapNumber} - delta ${delta}`}
      </text>
      <text x="14" y="106" className="stint-tooltip__line">
        {`Tyre life ${point.tyreLife ?? "N/A"} - ${getStintStatusLabel(point.trackStatus)}`}
      </text>
      <text x="14" y="126" className="stint-tooltip__muted">
        {point.lapPosition == null ? "Position N/A" : `Position P${point.lapPosition}`}
      </text>
    </g>
  );
}

function buildPlotPath(points: Array<{ plotX: number; plotY: number }>) {
  return points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.plotX.toFixed(2)} ${point.plotY.toFixed(2)}`)
    .join(" ");
}

function buildTrendPath(
  item: StintSeries & { points: PlottedStintPoint[] },
  scaleY: (valueMs: number) => number,
) {
  if (item.points.length < 2 || item.degradationMsPerLap == null) {
    return null;
  }

  const first = item.points[0];
  const last = item.points[item.points.length - 1];
  const startY = first.lapTimeMs;
  const endY = startY + item.degradationMsPerLap * (last.lapNumber - first.lapNumber);
  return `M ${first.plotX.toFixed(2)} ${scaleY(startY).toFixed(2)} L ${last.plotX.toFixed(2)} ${scaleY(endY).toFixed(2)}`;
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
