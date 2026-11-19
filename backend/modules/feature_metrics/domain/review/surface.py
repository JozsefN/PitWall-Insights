from ..race_estimation.common import finite
from ..strategy.spatial import (
    mapped_terrain,
    nearest_recovery_distance,
    polygon_clearance,
)


def surface_review(data, cutoff, profile):
    if not profile or not (profile.zones or profile.recovery_points_m):
        return {
            "availability": "unavailable",
            "reason": "A surveyed track profile registered to this session's coordinates is required.",
            "zones": [],
            "cars": [],
            "recovery_points_m": [],
        }
    cars = []
    for entry in data.entries:
        if not entry.positions:
            continue
        row = entry.positions[-1]
        if not 0 <= cutoff - row["session_time_ms"] <= 2000 or not all(
            finite(row.get(key)) for key in ("x", "y")
        ):
            continue
        point = [row[key] * 0.1 for key in ("x", "y")]
        if not any(point):
            continue
        distances = [
            (zone, polygon_clearance(point, zone.polygon_m))
            for zone in profile.zones
            if zone.kind != "marshal_sector"
        ]
        surface = [
            clearance for zone, clearance in distances if zone.kind == "racing_surface"
        ]
        clearance = max(surface) if surface else None
        kinds = sorted(
            {
                zone.kind
                for zone, distance in distances
                if distance > profile.position_error_m
            }
        )
        outside = (
            clearance is not None
            and clearance < -profile.position_error_m
            and "pit_lane" not in kinds
        )
        cars.append(
            {
                "entry_id": entry.id,
                "x_m": point[0],
                "y_m": point[1],
                "contained_in": kinds,
                "terrain": (
                    mapped_terrain(distances, profile.position_error_m)
                    if outside
                    else None
                ),
                "nearest_recovery_m": nearest_recovery_distance(point, profile),
                "inside_track_clearance_m": clearance,
                "beyond_mapped_track_candidate": outside,
            }
        )
    return {
        "availability": "calibrated_profile",
        "source_uri": profile.source_uri,
        "source_license": profile.source_license,
        "circuit_length_m": profile.circuit_length_m,
        "recovery_points_m": profile.recovery_points_m,
        "coordinate_frame": profile.coordinate_frame,
        "position_error_m": profile.position_error_m,
        "zones": [zone.model_dump(mode="json") for zone in profile.zones],
        "cars": cars,
        "reason": "Distance is relative to mapped polygons. Official track limits require race-control evidence.",
    }
