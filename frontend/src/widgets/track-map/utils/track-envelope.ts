import type { TrackMapPoint } from "../models";
import { sampleSmoothCircuit } from "./track-curves.ts";
import { illustratedRoadWidthLimitM, metresToMapUnits } from "./track-scale.ts";

type XY = { x: number; y: number };
export type IllustratedTrackEdges = { left: TrackMapPoint[]; right: TrackMapPoint[] };

// Use nearby repeated passes to shape an illustration. The position feed does
// not supply surveyed edges or reliable lateral placement.
export function illustrateTrackEdges(
  outline: TrackMapPoint[],
  passes: XY[][],
  widthLimitM = illustratedRoadWidthLimitM(),
): IllustratedTrackEdges | undefined {
  if (outline.length < 3) return undefined;

  const points = sampleSmoothCircuit(outline, metresToMapUnits(6), metresToMapUnits(1.5));
  if (points.length < 3) return undefined;

  const cellSize = 300;
  const cellKey = (x: number, y: number) => `${x},${y}`;
  const grid = new Map<string, number[]>();
  const normals = points.map((point, index) => {
    const next = points[(index + 1) % points.length];
    const dx = next.x - point.x;
    const dy = next.y - point.y;
    const length = Math.hypot(dx, dy);
    const key = cellKey(Math.floor(point.x / cellSize), Math.floor(point.y / cellSize));
    const cell = grid.get(key);
    if (cell) cell.push(index);
    else grid.set(key, [index]);
    return { dx: dx / length, dy: dy / length, length };
  });
  const offsets = points.map((): number[] => []);
  for (const pass of passes) {
    for (const sample of pass) {
      const column = Math.floor(sample.x / cellSize);
      const row = Math.floor(sample.y / cellSize);
      let bestSegment = -1;
      let bestOffset = 0;
      let bestDistanceSquared = 220 ** 2;
      for (let x = column - 1; x <= column + 1; x++) {
        for (let y = row - 1; y <= row + 1; y++) {
          for (const index of grid.get(cellKey(x, y)) ?? []) {
            const normal = normals[index];
            const dx = sample.x - points[index].x;
            const dy = sample.y - points[index].y;
            const longitudinal = dx * normal.dx + dy * normal.dy;
            const lateral = dy * normal.dx - dx * normal.dy;
            const outsideSegment = longitudinal - Math.max(0, Math.min(normal.length, longitudinal));
            const distanceSquared = lateral * lateral + outsideSegment * outsideSegment;
            if (distanceSquared >= bestDistanceSquared) continue;
            bestDistanceSquared = distanceSquared;
            bestOffset = lateral;
            bestSegment = index;
          }
        }
      }
      if (bestSegment >= 0) offsets[bestSegment].push(bestOffset);
    }
  }

  function wrap(index: number) { return ((index % points.length) + points.length) % points.length; }
  const maxWidth = metresToMapUnits(widthLimitM);
  const minimumSide = Math.min(metresToMapUnits(5.5), maxWidth / 2);
  const defaultSide = Math.min(metresToMapUnits(6.5), maxWidth / 2);
  const widths = offsets.map((_, index) => {
    const local = Array.from({ length: 9 }, (_, offset) => offsets[wrap(index + offset - 4)]).flat().sort((a, b) => a - b);
    // Keep a visible road when the cars all use the same line. Clamp the
    // illustration so pits, excursions and sparse samples cannot fan it out.
    if (local.length < 8) return { left: defaultSide, right: defaultSide };
    const margin = metresToMapUnits(4.2);
    const left = Math.max(minimumSide, local[Math.floor(local.length * 0.9)] + margin);
    const right = Math.max(minimumSide, margin - local[Math.floor(local.length * 0.1)]);
    if (left + right <= maxWidth) return { left, right };
    const remaining = maxWidth - 2 * minimumSide;
    const leftShare = (left - minimumSide) / (left + right - 2 * minimumSide);
    return { left: minimumSide + remaining * leftShare, right: minimumSide + remaining * (1 - leftShare) };
  });
  const left: TrackMapPoint[] = [];
  const right: TrackMapPoint[] = [];
  points.forEach((point, index) => {
    const previous = points[wrap(index - 1)];
    const next = points[wrap(index + 1)];
    const dx = next.x - previous.x;
    const dy = next.y - previous.y;
    const length = Math.hypot(dx, dy) || 1;
    const nearby = [-2, -1, 0, 1, 2].map((offset) => widths[wrap(index + offset)]);
    const a = nearby.reduce((sum, width) => sum + width.left, 0) / nearby.length;
    const b = nearby.reduce((sum, width) => sum + width.right, 0) / nearby.length;
    left.push({ ...point, x: point.x - a * dy / length, y: point.y + a * dx / length });
    right.push({ ...point, x: point.x + b * dy / length, y: point.y - b * dx / length });
  });
  return { left, right };
}
