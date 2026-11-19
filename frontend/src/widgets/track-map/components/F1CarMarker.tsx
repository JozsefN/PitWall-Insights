import type { TrackMapPoint } from "../models";

type F1CarMarkerProps = {
  point: TrackMapPoint;
  headingDeg: number;
  color: string;
  label: string;
  length: number;
  width: number;
};

export function F1CarMarker({
  point,
  headingDeg,
  color,
  label,
  length,
  width,
}: F1CarMarkerProps) {
  return (
    <g
      className="track-map-car"
      transform={`translate(${point.x} ${point.y}) rotate(${headingDeg}) scale(${length} ${width})`}
      aria-label={label}
    >
      <path d="M -.39 -.5 H -.25 V -.3 H -.39 Z M -.39 .3 H -.25 V .5 H -.39 Z M .24 -.5 H .37 V -.31 H .24 Z M .24 .31 H .37 V .5 H .24 Z" fill="#171611" />
      <path
        d="M -.5 -.4 H -.39 V -.21 L -.17 -.27 H -.06 Q .06 -.20 .14 -.09 H .37 V -.43 H .44 V -.075 L .5 0 L .44 .075 V .43 H .37 V .09 H .14 Q .06 .20 -.06 .27 H -.17 L -.39 .21 V .4 H -.5 Z"
        fill={color}
        stroke="#faf6e9"
        strokeWidth="0.65"
        vectorEffect="non-scaling-stroke"
      />
      <ellipse cx="0.01" cy="0" rx="0.092" ry="0.105" fill="#241d19" />
    </g>
  );
}
