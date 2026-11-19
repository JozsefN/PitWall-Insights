import type { CircuitRoadAsset } from "../../../features/circuits/circuit-catalog";
import type { TrackMapData, TrackMapOverlay } from "../models";
import type { useCircuitPitMap } from "../hooks/use-circuit-pit-map";
import { surfaceColours } from "../utils/circuit-overlays";

export function CircuitPitNotice({
  pitMap,
}: {
  pitMap: ReturnType<typeof useCircuitPitMap>;
}) {
  if (pitMap.pits?.source === "pit_reports") return null;
  let message: string;
  if (pitMap.pits?.source === "position_traces") {
    message = "Pit lane estimated from recorded entries and exits.";
  } else if (pitMap.preparationFailed) {
    message = "Pit position traces could not be loaded.";
  } else if (pitMap.isPreparing) {
    message = "Preparing pit lane from position traces…";
  } else if (pitMap.isError) {
    message = "Pit information could not be loaded.";
  } else if (pitMap.isLoading) {
    message = "Loading pit lane…";
  } else {
    message =
      "Pit lane unavailable. This session has insufficient entry and exit traces.";
  }
  return (
    <p className="circuit-map-layers__note" role="status">
      {message}
    </p>
  );
}

export function CircuitRoadNotice({
  asset,
  hasOutline,
}: {
  asset?: CircuitRoadAsset;
  hasOutline: boolean;
}) {
  return (
    <p className="circuit-map-layers__note">
      {asset ? (
        <>
          {asset.width === "estimated"
            ? "Mapped centreline with estimated width."
            : "Mapped road edges."}{" "}
          Car positions are approximate. Geometry by{" "}
          {asset.credits.map(({ label, url }, index) => (
            <span key={url}>
              {index ? " · " : ""}
              <a href={url} target="_blank" rel="noreferrer">
                {label}
              </a>
            </span>
          ))}
        </>
      ) : hasOutline ? (
        "Track edges estimated around a reference lap. Position across the track is approximate."
      ) : (
        "A complete lap outline is unavailable in the loaded positions."
      )}
    </p>
  );
}

export function CircuitConditionNotes({
  overlay,
  data,
  hasWeatherReport,
}: {
  overlay: TrackMapOverlay;
  data: TrackMapData;
  hasWeatherReport: boolean;
}) {
  const { layer, weather, flags, surface } = overlay;
  const unmapped = flags?.sectors.some(
    ({ number }) =>
      !surface?.zones.some(
        (zone) =>
          zone.kind === "marshal_sector" && zone.sector_number === number,
      ),
  );
  const hasLocalCaution =
    flags && (flags.sectors.length || flags.unlocated_caution);
  const flagHeadline =
    hasLocalCaution &&
    (!flags?.track_flag || ["GREEN", "CLEAR"].includes(flags.track_flag))
      ? "Local caution"
      : (flags?.track_flag ?? "No active flag report");
  return (
    <>
      {layer === "weather" && hasWeatherReport ? (
        <p className="circuit-map-layers__note">
          {weather ? (
            <>
              <strong>
                {weather.rain_reported == null
                  ? "Rain status missing"
                  : weather.rain_reported
                    ? "Rain reported"
                    : "No rain reported"}
              </strong>{" "}
              · Circuit-wide weather. Surface wetness by corner is unavailable.
              Arrows show the reported north-referenced bearing.
            </>
          ) : (
            "No fresh weather report at this time."
          )}
        </p>
      ) : null}
      {flags ? (
        <p className="circuit-map-layers__note">
          <strong>{flagHeadline}</strong>
          {flags.sectors
            .map(
              ({ number, flag }) => ` · Sector ${number} ${flag.toLowerCase()}`,
            )
            .join("")}
          {unmapped || flags.unlocated_caution
            ? " · Exact boundaries unavailable"
            : ""}
        </p>
      ) : null}
      {layer === "surface" && surface ? (
        <p className="circuit-map-layers__note">
          {surface.availability === "calibrated_profile" ? (
            <>
              <span className="circuit-map-legend">
                {Object.entries({
                  racing_surface: "Track",
                  pit_lane: "Pit lane",
                  gravel: "Gravel",
                  runoff: "Runoff",
                  recovery: "Recovery access",
                })
                  .filter(
                    ([kind]) =>
                      surface.zones.some((zone) => zone.kind === kind) ||
                      (kind === "recovery" &&
                        surface.recovery_points_m?.length),
                  )
                  .map(([kind, label]) => (
                    <span key={kind}>
                      <i
                        aria-hidden="true"
                        style={{ background: surfaceColours[kind] }}
                      />
                      {label}
                    </span>
                  ))}
              </span>
              {surface.circuit_length_m
                ? ` · ${(surface.circuit_length_m / 1000).toFixed(3)} km`
                : ""}
              {surface.position_error_m
                ? ` · Position tolerance ${surface.position_error_m} m`
                : ""}
              {surface.source_uri?.startsWith("https://") ? (
                <>
                  {" "}
                  ·{" "}
                  <a href={surface.source_uri} target="_blank" rel="noreferrer">
                    {surface.source_license ?? "Geometry source"}
                  </a>
                </>
              ) : null}
            </>
          ) : (
            surface.reason
          )}
        </p>
      ) : null}
      {layer === "surface" && surface?.cars.some((car) => car.terrain) ? (
        <ul className="circuit-map-layers__note">
          {surface.cars
            .filter((car) => car.terrain)
            .map((car) => (
              <li key={car.entry_id}>
                {data.drivers?.find((driver) => driver.key === car.entry_id)
                  ?.label ??
                  data.traces.find((trace) => trace.key === car.entry_id)
                    ?.shortLabel ??
                  "Car"}{" "}
                · Mapped {car.terrain}
                {car.nearest_recovery_m == null
                  ? ""
                  : ` · ${Math.round(car.nearest_recovery_m)} m straight line to mapped access`}
              </li>
            ))}
        </ul>
      ) : null}
    </>
  );
}
