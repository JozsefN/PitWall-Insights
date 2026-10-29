"""Download reviewable OSM raceway/service lines; never invent track-boundary or recovery polygons."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser()
parser.add_argument(
    "--bbox",
    nargs=4,
    type=float,
    required=True,
    metavar=("SOUTH", "WEST", "NORTH", "EAST"),
)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--endpoint", choices=("de", "kumi"), default="de")
args = parser.parse_args()
south, west, north, east = args.bbox
if (
    not -90 <= south < north <= 90
    or not -180 <= west < east <= 180
    or north - south > 0.05
    or east - west > 0.05
):
    raise ValueError(
        "Use a valid small circuit bounding box (at most 0.05 degrees per axis)"
    )
box = ",".join(str(value) for value in args.bbox)
query = f'[out:json][timeout:15];way["highway"~"^(raceway|service|escape)$"]({box});out geom;'
host = (
    "https://overpass-api.de/api/interpreter"
    if args.endpoint == "de"
    else "https://overpass.kumi.systems/api/interpreter"
)
url = host + "?" + urlencode({"data": query})
with urlopen(
    Request(url, headers={"User-Agent": "PitWall-Insights-strategy-research/1.0"}),
    timeout=20,
) as response:
    raw = response.read(4_000_001)
if len(raw) > 4_000_000:
    raise ValueError("Map response exceeds four megabytes")
payload = json.loads(raw)
features = []
for way in payload.get("elements", []):
    points = way.get("geometry", [])
    if len(points) < 2:
        continue
    features.append(
        dict(
            type="Feature",
            geometry=dict(
                type="LineString",
                coordinates=[[point["lon"], point["lat"]] for point in points],
            ),
            properties=dict(
                osm_way_id=way["id"],
                tags=way.get("tags", {}),
                verified_track_boundary=False,
                verified_recovery_route=False,
            ),
        )
    )
output = dict(
    type="FeatureCollection",
    features=features,
    attribution="OpenStreetMap contributors",
    license="ODbL-1.0",
    license_url="https://www.openstreetmap.org/copyright",
    source_uri=url,
    downloaded_at=datetime.now(timezone.utc).isoformat(),
    coordinate_frame="WGS84 longitude/latitude degrees",
    warnings=[
        "Lines are map candidates, not surveyed racing-surface edges or verified marshal access.",
        "Metric georegistration and source review are required before creating a strategy track profile.",
    ],
)
args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
print(
    json.dumps(
        {
            "candidate_ways": len(features),
            "database_modified": False,
            "output": str(args.output),
        }
    )
)
