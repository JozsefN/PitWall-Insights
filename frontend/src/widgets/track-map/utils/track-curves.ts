type XY = { x: number; y: number };
type Cubic = { from: XY; first: XY; second: XY; to: XY };

function unit(x: number, y: number): XY {
  const length = Math.hypot(x, y);
  return length ? { x: x / length, y: y / length } : { x: 0, y: 0 };
}

export function movementDirection(from: XY, to: XY) {
  return unit(to.x - from.x, to.y - from.y);
}

export function blendedDirection(first: XY, second: XY) {
  return unit(first.x + second.x, first.y + second.y);
}

export function boundedCurve(
  from: XY, to: XY, start: XY, end: XY, maxDeviation: number,
  requestedHandles?: { start: number; end: number },
): Cubic {
  const distance = Math.hypot(to.x - from.x, to.y - from.y);
  const chord = movementDirection(from, to);
  function handle(direction: XY, requested = distance / 3) {
    const along = direction.x * chord.x + direction.y * chord.y;
    if (along < 0) return 0;
    const sideways = Math.abs(direction.x * chord.y - direction.y * chord.x);
    return Math.min(requested, distance / 2, sideways > 0 ? maxDeviation / sideways : Infinity);
  }
  const a = handle(start, requestedHandles?.start);
  const b = handle(end, requestedHandles?.end);
  return {
    from,
    first: { x: from.x + start.x * a, y: from.y + start.y * a },
    second: { x: to.x - end.x * b, y: to.y - end.y * b },
    to,
  };
}

export function curvePoint(curve: Cubic, t: number) {
  const u = 1 - t;
  const { from, first, second, to } = curve;
  return {
    x: u ** 3 * from.x + 3 * u ** 2 * t * first.x + 3 * u * t ** 2 * second.x + t ** 3 * to.x,
    y: u ** 3 * from.y + 3 * u ** 2 * t * first.y + 3 * u * t ** 2 * second.y + t ** 3 * to.y,
  };
}

export function curveHeading(curve: Cubic, t: number) {
  const u = 1 - t;
  const { from, first, second, to } = curve;
  const dx = u * u * (first.x - from.x) + 2 * u * t * (second.x - first.x) + t * t * (to.x - second.x);
  const dy = u * u * (first.y - from.y) + 2 * u * t * (second.y - first.y) + t * t * (to.y - second.y);
  const heading = dx || dy ? Math.atan2(dy, dx) : Math.atan2(to.y - from.y, to.x - from.x);
  return heading * 180 / Math.PI;
}

function curveSegments<T extends XY>(points: T[], closed: boolean, maxDeviation: number) {
  const vertices = points.filter((point, index) => {
    if (!index) return true;
    const previous = points[index - 1];
    return Math.hypot(point.x - previous.x, point.y - previous.y) > 0.05;
  });
  if (closed && vertices.length > 1) {
    const first = vertices[0];
    const last = vertices[vertices.length - 1];
    if (Math.hypot(first.x - last.x, first.y - last.y) <= 0.05) vertices.pop();
  }
  const count = vertices.length;
  if (count < 2) return [];
  const directions = vertices.map((point, index) => {
    const previous = vertices[index - 1] ?? (closed ? vertices[count - 1] : undefined);
    const next = vertices[index + 1] ?? (closed ? vertices[0] : undefined);
    const incoming = previous ? movementDirection(previous, point) : { x: 0, y: 0 };
    const outgoing = next ? movementDirection(point, next) : { x: 0, y: 0 };
    return blendedDirection(incoming, outgoing);
  });
  return Array.from({ length: closed ? count : count - 1 }, (_, index) => {
    const next = (index + 1) % count;
    return {
      source: vertices[index],
      curve: boundedCurve(vertices[index], vertices[next], directions[index], directions[next], maxDeviation),
    };
  });
}

export function sampleSmoothCircuit<T extends XY>(points: T[], spacing: number, maxDeviation: number) {
  return curveSegments(points, true, maxDeviation).flatMap(({ source, curve }) => {
    const steps = Math.max(1, Math.ceil(Math.hypot(curve.to.x - curve.from.x, curve.to.y - curve.from.y) / spacing));
    return Array.from({ length: steps }, (_, step) => ({ ...source, ...curvePoint(curve, step / steps) }));
  });
}

export function smoothTrackPath(points: XY[], closed: boolean, maxDeviation: number) {
  if (!points.length) return "";
  const format = ({ x, y }: XY) => `${x.toFixed(2)} ${y.toFixed(2)}`;
  const curves = curveSegments(points, closed, maxDeviation);
  if (!curves.length) return `M ${format(points[0])}`;
  const commands = curves.map(({ curve }) => `C ${format(curve.first)} ${format(curve.second)} ${format(curve.to)}`);
  return [`M ${format(curves[0].curve.from)}`, ...commands, ...(closed ? ["Z"] : [])].join(" ");
}
