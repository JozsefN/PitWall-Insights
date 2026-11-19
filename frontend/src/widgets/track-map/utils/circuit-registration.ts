import type { RoadSample } from "../../../data/circuit-road-csv.ts";
import type { MappedRoad } from "./mapped-road.ts";
import { buildMappedRoad, roadMatchesLap } from "./mapped-road.ts";

type Point = { x: number; y: number };
type Fit = { angle: number; x: number; y: number };

function resample(points: Point[], count: number) {
  const arcs = [0];
  const closed = [...points, points[0]];
  for (let index = 1; index < closed.length; index++) {
    arcs.push(
      arcs[index - 1] +
        Math.hypot(
          closed[index].x - closed[index - 1].x,
          closed[index].y - closed[index - 1].y,
        ),
    );
  }
  const length = arcs[arcs.length - 1];
  let at = 1;
  const samples = Array.from({ length: count }, (_, index) => {
    const target = (length * index) / count;
    while (arcs[at] <= target && at < arcs.length - 1) at++;
    const fraction = (target - arcs[at - 1]) / (arcs[at] - arcs[at - 1] || 1);
    const start = closed[at - 1];
    return {
      x: start.x + fraction * (closed[at].x - start.x),
      y: start.y + fraction * (closed[at].y - start.y),
    };
  });
  return { samples, length };
}

function centroid(points: Point[]) {
  const sum = points.reduce(
    (total, point) => ({ x: total.x + point.x, y: total.y + point.y }),
    { x: 0, y: 0 },
  );
  return { x: sum.x / points.length, y: sum.y / points.length };
}

function rigidFit(from: Point[], to: Point[]): Fit {
  const a = centroid(from);
  const b = centroid(to);
  let dot = 0;
  let cross = 0;
  from.forEach((point, i) => {
    const x = point.x - a.x,
      y = point.y - a.y;
    const u = to[i].x - b.x,
      v = to[i].y - b.y;
    dot += x * u + y * v;
    cross += x * v - y * u;
  });
  const angle = Math.atan2(cross, dot);
  const relative = transform(a, { angle, x: 0, y: 0 });
  return { angle, x: b.x - relative.x, y: b.y - relative.y };
}

function transform(point: Point, fit: Fit): Point {
  const c = Math.cos(fit.angle),
    s = Math.sin(fit.angle);
  return {
    x: c * point.x - s * point.y + fit.x,
    y: s * point.x + c * point.y + fit.y,
  };
}

function nearest(point: Point, ring: Point[]) {
  let best = ring[0],
    error = Infinity;
  ring.forEach((start, i) => {
    const end = ring[(i + 1) % ring.length];
    const dx = end.x - start.x,
      dy = end.y - start.y;
    const fraction = Math.max(
      0,
      Math.min(
        1,
        ((point.x - start.x) * dx + (point.y - start.y) * dy) /
          (dx * dx + dy * dy || 1),
      ),
    );
    const x = start.x + fraction * dx,
      y = start.y + fraction * dy;
    const distance = (x - point.x) ** 2 + (y - point.y) ** 2;
    if (distance < error) {
      best = { x, y };
      error = distance;
    }
  });
  return best;
}

export function registerCircuitRoad(
  rows: readonly RoadSample[],
  outline: readonly Point[],
): MappedRoad | undefined {
  if (rows.length < 30 || outline.length < 32) return undefined;
  const source = rows.map(([x, y]) => ({ x, y }));
  const target = outline.map(({ x, y }) => ({ x: x / 10, y: y / 10 }));
  const a = resample(source, 128),
    b = resample(target, 128);
  if (
    !Number.isFinite(a.length) ||
    !Number.isFinite(b.length) ||
    a.length < 500 ||
    b.length < a.length * 0.9 ||
    b.length > a.length * 1.1
  )
    return undefined;
  let error = Infinity;
  let fit: Fit | undefined;
  for (const ordered of [a.samples, [...a.samples].reverse()]) {
    for (let shift = 0; shift < ordered.length; shift++) {
      const shifted = ordered.map(
        (_, i) => ordered[(i + shift) % ordered.length],
      );
      const candidate = rigidFit(shifted, b.samples);
      const loss = shifted.reduce((sum, point, i) => {
        const fitted = transform(point, candidate);
        return (
          sum +
          (fitted.x - b.samples[i].x) ** 2 +
          (fitted.y - b.samples[i].y) ** 2
        );
      }, 0);
      if (loss < error) {
        fit = candidate;
        error = loss;
      }
    }
  }
  if (!fit || error / a.samples.length > 55 ** 2) return undefined;
  // Refine against the full sampled racing line while keeping a rigid scale.
  const fitSource = resample(source, 192).samples;
  for (let iteration = 0; iteration < 8; iteration++) {
    const current = fit;
    fit = rigidFit(
      fitSource,
      fitSource.map((point) => nearest(transform(point, current), target)),
    );
  }
  const c = Math.cos(fit.angle),
    s = Math.sin(fit.angle);
  const road = buildMappedRoad(rows, {
    angle: -fit.angle,
    east: -c * fit.x - s * fit.y,
    north: s * fit.x - c * fit.y,
  });
  return roadMatchesLap(road, outline) ? road : undefined;
}
