import type { TrackMapPoint } from "../models";

type F1CarMarkerProps = {
  point: TrackMapPoint;
  headingDeg: number;
  color: string;
  label: string;
  size: number;
};

export function F1CarMarker({
  point,
  headingDeg,
  color,
  label,
  size,
}: F1CarMarkerProps) {
  const scale = size / 28;

  return (
    <g
      className="track-map-car"
      transform={`translate(${point.x} ${point.y}) rotate(${headingDeg}) scale(${scale})`}
      aria-label={label}
    >
      <rect x="-18" y="-9" width="7" height="18" rx="2" fill="#070b11" stroke="rgba(255,255,255,0.5)" strokeWidth="1.2" />
      <rect x="12" y="-10" width="5" height="20" rx="2" fill="#070b11" stroke="rgba(255,255,255,0.5)" strokeWidth="1.2" />
      <rect x="-10" y="-6" width="21" height="12" rx="5" fill={color} stroke="rgba(255,255,255,0.7)" strokeWidth="1.1" />
      <path d="M 9 -5 L 21 0 L 9 5 Z" fill={color} stroke="rgba(255,255,255,0.7)" strokeWidth="1.1" />
      <rect x="-17" y="-12" width="9" height="5" rx="2" fill="#070b11" />
      <rect x="-17" y="7" width="9" height="5" rx="2" fill="#070b11" />
      <rect x="5" y="-13" width="8" height="5" rx="2" fill="#070b11" />
      <rect x="5" y="8" width="8" height="5" rx="2" fill="#070b11" />
      <ellipse cx="-1" cy="0" rx="4" ry="3" fill="rgba(255,255,255,0.85)" />
      <circle cx="21" cy="0" r="2.8" fill="rgba(255,255,255,0.92)" />
    </g>
  );
}
