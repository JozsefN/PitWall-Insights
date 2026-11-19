import { parseRoadCsv } from "../circuit-road-csv";

export async function getCircuitRoad(file: string, signal: AbortSignal) {
  const response = await fetch(
    import.meta.env.BASE_URL + "circuit-roads/" + file,
    { signal },
  );
  if (!response.ok)
    throw new Error(`Circuit road returned HTTP ${response.status}`);
  const road = parseRoadCsv(await response.text());
  if (!road) throw new Error(`Invalid circuit road: ${file}`);
  return road;
}
