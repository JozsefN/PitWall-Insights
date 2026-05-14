import type { SessionCircuitCornerDto } from "../../../data/contracts/sessions.contracts";
import type { TrackMapTurnMarker } from "../models";

export function buildTrackMapTurnMarkers(
  corners: SessionCircuitCornerDto[] | undefined,
): TrackMapTurnMarker[] {
  return (corners ?? [])
    .filter((corner) => Number.isFinite(corner.x) && Number.isFinite(corner.y))
    .map((corner) => ({
      key: `${corner.number}${corner.letter ?? ""}`,
      label: `${corner.number}${corner.letter ?? ""}`,
      x: corner.x,
      y: corner.y,
      angleDeg: corner.angle_deg,
      distanceM: corner.distance_m,
    }));
}
