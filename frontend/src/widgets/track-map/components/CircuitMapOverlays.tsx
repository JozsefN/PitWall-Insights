import { memo, type CSSProperties } from "react";
import type { TrackMapOverlay } from "../models";
import { flagColours, surfaceColours } from "../utils/circuit-overlays";
import { metresToMapUnits } from "../utils/track-scale";

export function CircuitSurfaceOverlay({
  overlay,
  radius,
}: {
  overlay: TrackMapOverlay;
  radius: number;
}) {
  if (
    !overlay.surface ||
    (overlay.layer !== "surface" && overlay.layer !== "flags")
  )
    return null;
  const flags = new Map(
    overlay.flags?.sectors.map(({ number, flag }) => [number, flag]),
  );
  return (
    <g className="circuit-surface-overlay">
      {overlay.surface.zones.map((zone) => {
        const fill =
          overlay.layer === "flags" && zone.sector_number != null
            ? flagColours[flags.get(zone.sector_number) ?? ""]
            : overlay.layer === "surface"
              ? surfaceColours[zone.kind]
              : undefined;
        if (!fill) return null;
        return (
          <polygon
            key={zone.zone_id}
            data-zone-kind={zone.kind}
            points={zone.polygon_m
              .map(([x, y]) => `${metresToMapUnits(x)},${metresToMapUnits(y)}`)
              .join(" ")}
            fill={fill}
            stroke={fill}
            fillOpacity={overlay.layer === "flags" ? 0.34 : 0.55}
            vectorEffect="non-scaling-stroke"
          >
            <title>
              {zone.sector_number
                ? `Marshal sector ${zone.sector_number}`
                : zone.zone_id}
            </title>
          </polygon>
        );
      })}
      {overlay.layer === "surface"
        ? overlay.surface.recovery_points_m?.map(([x, y], index) => (
            <circle
              key={index}
              cx={metresToMapUnits(x)}
              cy={metresToMapUnits(y)}
              r={radius}
              fill="#101b28"
              stroke="#7ad9e6"
              vectorEffect="non-scaling-stroke"
            >
              <title>Mapped recovery access {index + 1}</title>
            </circle>
          ))
        : null}
    </g>
  );
}

const windArrows = Array.from({ length: 28 }, (_, index) => index);

export const WindField = memo(function WindField({
  weather,
}: {
  weather: NonNullable<TrackMapOverlay["weather"]>;
}) {
  const { wind_direction_deg: direction, wind_speed_ms: speed } = weather;
  const hasBearing = direction != null && Number.isFinite(direction);
  const speedKph = speed != null && Number.isFinite(speed) ? speed * 3.6 : null;
  const bearing = (direction ?? 0) * Math.PI / 180;
  const windStyle = {
    "--wind-angle": `${direction ?? 0}deg`,
    "--wind-x": `${Math.sin(bearing) * 45}px`,
    "--wind-y": `${-Math.cos(bearing) * 45}px`,
    "--wind-duration": `${Math.max(1.8, Math.min(7, 40 / (speedKph ?? 1)))}s`,
  } as CSSProperties;
  return (
    <>
      {hasBearing && speedKph != null && speedKph > 0 ? (
        <div className="circuit-wind-field" style={windStyle} data-bearing={direction} aria-hidden="true">
          <div className="circuit-wind-field__arrows">
            {windArrows.map((index) => <span key={index}>&uarr;</span>)}
          </div>
        </div>
      ) : null}
      {speedKph === null ? null : <strong className="circuit-wind-speed" aria-label={`Reported wind speed ${speedKph.toFixed(1)} kilometres per hour`}>{speedKph.toFixed(1)} km/h</strong>}
    </>
  );
});
