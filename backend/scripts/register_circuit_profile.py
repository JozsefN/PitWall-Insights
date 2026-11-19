"""Build an owned strategy-context payload from a licensed circuit GeoJSON export."""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from modules.feature_metrics.domain.strategy.georegistration import (
    align_metric_landmarks,
)
from modules.feature_metrics.domain.strategy.models import StrategyContext


def prepare_profile(geojson, metadata):
    """Coordinates are survey east/north metres unless a WGS84 origin is supplied."""
    if geojson.get("type") != "FeatureCollection":
        raise ValueError("Supply a GeoJSON FeatureCollection")
    origin = metadata.get("origin_lon_lat")
    if origin is not None:
        lon, lat = origin
        if not (-180 <= lon <= 180 and -90 < lat < 90):
            raise ValueError("Invalid local survey origin")
        radians = math.radians(lat)
        flattening_term = 1 - 0.00669437999014 * math.sin(radians) ** 2
        east_radius = 6_378_137 * math.cos(radians) / math.sqrt(flattening_term)
        north_radius = 6_378_137 * (1 - 0.00669437999014) / flattening_term**1.5

    def east_north(point):
        x, y = point[:2]
        if origin is None:
            return np.array([x, y], dtype=float)
        if (
            not (-180 <= x <= 180 and -90 <= y <= 90)
            or max(abs(x - lon), abs(y - lat)) > 0.2
        ):
            raise ValueError(
                "Survey positions must be longitude, latitude near the circuit origin"
            )
        return np.array(
            [
                east_radius * math.radians(x - lon),
                north_radius * math.radians(y - lat),
            ]
        )

    landmarks = metadata["landmarks"]
    alignment = align_metric_landmarks(
        [item["track_xy_m"] for item in landmarks],
        [east_north(item["survey"]) for item in landmarks],
        survey_error_m=metadata.get("survey_error_m", 3),
        max_residual_m=metadata.get("max_residual_m", 10),
    )
    rotation = np.array(alignment["rotation_track_to_enu"])
    offset = np.array(alignment["translation_enu_m"])

    def in_track_frame(point):
        return ((east_north(point) - offset) @ rotation / alignment["scale"]).tolist()

    zones = []
    recovery = []
    for index, feature in enumerate(geojson["features"], 1):
        properties = feature.get("properties") or {}
        geometry = feature["geometry"]
        coordinates = geometry["coordinates"]
        kind = properties["kind"]
        if kind == "recovery_access" and geometry["type"] == "Point":
            recovery.append(in_track_frame(coordinates))
        elif geometry["type"] == "Polygon" and len(coordinates) == 1:
            ring = coordinates[0]
            if ring and ring[0] == ring[-1]:
                ring = ring[:-1]
            zones.append(
                {
                    "zone_id": properties.get("id", f"zone-{index}"),
                    "kind": kind,
                    "sector_number": properties.get("sector_number"),
                    "polygon_m": [in_track_frame(point) for point in ring],
                }
            )
        else:
            raise ValueError(
                f"Feature {index} requires one simple polygon or a recovery Point"
            )
    if not (zones or recovery):
        raise ValueError("Supply at least one circuit polygon or recovery point")

    fields = (
        "circuit_key",
        "coordinate_frame",
        "source_uri",
        "source_license",
        "valid_season_from",
        "valid_season_to",
    )
    track = {key: metadata[key] for key in fields}
    if "circuit_length_m" in metadata:
        track["circuit_length_m"] = metadata["circuit_length_m"]
    context = StrategyContext.model_validate(
        {
            "known_at_ms": 0,
            "source_note": f"{metadata['source_license']}. Landmark registration maximum residual {alignment['residual_max_m']:.2f} m.",
            "track": {
                **track,
                "north_angle_xy_deg": alignment["north_angle_xy_deg"],
                "alignment_error_deg": alignment["alignment_error_deg"],
                "position_error_m": alignment["position_error_m"],
                "zones": zones,
                "recovery_points_m": recovery,
            },
        }
    )
    return context.model_dump(mode="json", exclude_none=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("geojson", type=Path)
    parser.add_argument("metadata", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            prepare_profile(
                json.loads(args.geojson.read_text(encoding="utf-8")),
                json.loads(args.metadata.read_text(encoding="utf-8")),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
