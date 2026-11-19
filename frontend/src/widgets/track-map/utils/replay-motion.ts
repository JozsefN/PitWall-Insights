import type { TrackMapPoint } from "../models";
import { nextPointIndex } from "./geometry.ts";
import { boundedCurve, curveHeading, curvePoint, movementDirection } from "./track-curves.ts";
import { metresToMapUnits } from "./track-scale.ts";

const playbackDelayMs = 1200;
const maximumGapMs = 2200;
const minimumHeadingDistance = metresToMapUnits(0.8);
const maxPositionCorrection = metresToMapUnits(0.9);

type Direction = ReturnType<typeof movementDirection>;
type MotionKnot = { point: TrackMapPoint; heading?: Direction; speed?: number };

export function adjoiningFixes(before: TrackMapPoint, after: TrackMapPoint) {
  const gap = after.sessionTimeMs - before.sessionTimeMs;
  const distance = Math.hypot(after.x - before.x, after.y - before.y);
  return gap > 0 && gap <= maximumGapMs && distance <= 1.4 * gap;
}

export function prepareReplayMotion(observed: TrackMapPoint[]) {
  // Build nearby knots on demand, including after seeks. The path is deterministic at a given replay time.
  const knots: (MotionKnot | undefined)[] = [];
  function knot(index: number): MotionKnot {
    if (knots[index]) return knots[index];
    const fix = observed[index];
    const before = observed[index - 1];
    const after = observed[index + 1];
    if (!before || !adjoiningFixes(before, fix)) return { point: fix };

    const incoming = Math.hypot(fix.x - before.x, fix.y - before.y);
    const incomingSpeed = incoming / (fix.sessionTimeMs - before.sessionTimeMs);
    let result: MotionKnot = { point: fix, speed: incomingSpeed };
    // A centered estimate is safe only when both neighbors are known by the time the incoming segment starts.
    if (after && after.sessionTimeMs - before.sessionTimeMs <= playbackDelayMs && adjoiningFixes(fix, after)) {
      const chord = movementDirection(before, after);
      const offset = (fix.y - before.y) * chord.x - (fix.x - before.x) * chord.y;
      // Correct only a small cross-track residual in the source samples. Keep along-track progress and larger moves.
      const correction = Math.max(-maxPositionCorrection, Math.min(maxPositionCorrection, offset * 0.65));
      const outgoingSpeed = Math.hypot(after.x - fix.x, after.y - fix.y) / (after.sessionTimeMs - fix.sessionTimeMs);
      if (Math.hypot(after.x - before.x, after.y - before.y) >= minimumHeadingDistance) {
        const totalSpeed = incomingSpeed + outgoingSpeed;
        result = {
          point: { ...fix, x: fix.x + correction * chord.y, y: fix.y - correction * chord.x },
          heading: chord,
          speed: totalSpeed > 0 ? 2 * incomingSpeed * outgoingSpeed / totalSpeed : 0,
        };
      }
    }
    if (!result.heading && incoming >= minimumHeadingDistance) result.heading = movementDirection(before, fix);
    if (!result.heading) {
      // Very small position changes do not identify a new heading when a car is stopped.
      for (let cursor = index - 1; cursor > 0; cursor--) {
        const older = observed[cursor - 1];
        const newer = observed[cursor];
        if (!adjoiningFixes(older, newer)) break;
        if (Math.hypot(newer.x - older.x, newer.y - older.y) < minimumHeadingDistance) continue;
        result.heading = movementDirection(older, newer);
        break;
      }
    }
    knots[index] = result;
    return result;
  }

  function headingDeg(direction?: Direction) {
    return direction ? Math.atan2(direction.y, direction.x) * 180 / Math.PI : 0;
  }

  return {
    pointAt: (index: number) => knot(index).point,
    marker(end: number, timeMs: number, animate: boolean) {
      if (!animate) {
        const index = end - 1;
        const point = observed[index];
        const previous = observed[index - 1];
        return { point, heading: previous && adjoiningFixes(previous, point) ? headingDeg(movementDirection(previous, point)) : 0 };
      }

      const target = timeMs - playbackDelayMs;
      const afterIndex = Math.min(end, nextPointIndex(observed, target));
      const before = knot(Math.max(0, afterIndex - 1));
      const next = observed[afterIndex];
      if (afterIndex === 0 || afterIndex === end || !adjoiningFixes(observed[afterIndex - 1], next)) {
        return { point: before.point, heading: headingDeg(before.heading) };
      }

      const after = knot(afterIndex);
      const interval = after.point.sessionTimeMs - before.point.sessionTimeMs;
      // When an update arrives late, continue from the held position at its arrival time.
      const start = Math.max(before.point.sessionTimeMs + playbackDelayMs, after.point.sessionTimeMs);
      const duration = after.point.sessionTimeMs + playbackDelayMs - start;
      const fraction = (timeMs - start) / duration;
      const startedLate = start === after.point.sessionTimeMs;
      const direction = movementDirection(before.point, after.point);
      const speed = Math.hypot(after.point.x - before.point.x, after.point.y - before.point.y) / interval;
      const curve = boundedCurve(
        before.point, after.point, before.heading ?? direction, after.heading ?? direction, maxPositionCorrection,
        { start: (before.speed ?? speed) * duration * (startedLate ? 0.025 : 1 / 3), end: (after.speed ?? speed) * duration / 3 },
      );
      return {
        point: { ...before.point, ...curvePoint(curve, fraction), sessionTimeMs: before.point.sessionTimeMs + interval * fraction },
        heading: speed * interval < minimumHeadingDistance ? headingDeg(before.heading ?? after.heading) : curveHeading(curve, fraction),
      };
    },
  };
}
