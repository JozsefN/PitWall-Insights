// Signed local coordinates and positive centre-to-edge offsets in metres.
export type RoadSample = readonly [
  x: number,
  y: number,
  right: number,
  left: number,
];

export function parseRoadCsv(csv: string): RoadSample[] | undefined {
  const rows: RoadSample[] = [];
  for (const raw of csv.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const fields = line.split(",").map((field) => field.trim());
    if (fields.length !== 4 || fields.some((field) => !field)) return undefined;
    const [x, y, right, left] = fields.map(Number);
    if (![x, y, right, left].every(Number.isFinite) || right <= 0 || left <= 0)
      return undefined;
    rows.push([x, y, right, left]);
  }
  return rows.length >= 30 ? rows : undefined;
}
