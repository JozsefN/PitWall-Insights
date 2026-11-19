import type { TrackMapPoint } from "../models";
import type { RoadSample } from "../../../data/circuit-road-csv.ts";
import { blendedDirection, movementDirection } from "./track-curves.ts";
import { metresToMapUnits } from "./track-scale.ts";

type Point = Pick<TrackMapPoint, "x" | "y">;

export type RoadTransform = { angle: number; east: number; north: number };

export type MappedRoad = {
  centre: Point[];
  edges: { left: Point[]; right: Point[] };
};

export function buildMappedRoad(
  rows: readonly RoadSample[],
  transform: RoadTransform,
): MappedRoad {
  const first = rows[0];
  const last = rows[rows.length - 1];
  const samples =
    Math.hypot(first[0] - last[0], first[1] - last[1]) < 0.1
      ? rows.slice(0, -1)
      : rows;
  const cosine = Math.cos(transform.angle);
  const sine = Math.sin(transform.angle);
  function inSessionFrame(east: number, north: number) {
    const x = east - transform.east;
    const y = north - transform.north;
    return {
      x: metresToMapUnits(cosine * x + sine * y),
      y: metresToMapUnits(-sine * x + cosine * y),
    };
  }

  const centre: Point[] = [];
  const left: Point[] = [];
  const right: Point[] = [];
  samples.forEach(([x, y, widthRight, widthLeft], index) => {
    const previous = samples[(index + samples.length - 1) % samples.length];
    const next = samples[(index + 1) % samples.length];
    const heading = blendedDirection(
      movementDirection({ x: previous[0], y: previous[1] }, { x, y }),
      movementDirection({ x, y }, { x: next[0], y: next[1] }),
    );
    centre.push(inSessionFrame(x, y));
    left.push(
      inSessionFrame(x - widthLeft * heading.y, y + widthLeft * heading.x),
    );
    right.push(
      inSessionFrame(x + widthRight * heading.y, y - widthRight * heading.x),
    );
  });
  return { centre, edges: { left, right } };
}

export function roadMatchesLap(road: MappedRoad, lap: readonly Point[]) {
  if (lap.length < 32) return false;
  // Allow for racing-line offsets and the error of an imagery-derived boundary.
  const toleranceSquared = metresToMapUnits(18) ** 2;
  const stride = Math.ceil(lap.length / 160);
  let matched = 0;
  for (let index = 0; index < lap.length; index += stride) {
    const point = lap[index];
    if (
      road.centre.some((start, index) => {
        const end = road.centre[(index + 1) % road.centre.length];
        const dx = end.x - start.x;
        const dy = end.y - start.y;
        const x = point.x - start.x;
        const y = point.y - start.y;
        const segmentLengthSquared = dx * dx + dy * dy;
        const along = Math.max(
          0,
          Math.min(1, (x * dx + y * dy) / (segmentLengthSquared || 1)),
        );
        return (
          (x - along * dx) ** 2 + (y - along * dy) ** 2 <= toleranceSquared
        );
      })
    )
      matched++;
  }
  return matched / Math.ceil(lap.length / stride) >= 0.92;
}
