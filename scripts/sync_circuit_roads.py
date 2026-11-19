"""Download the catalog's pinned sources and build one road CSV per venue."""

import json
from concurrent.futures import ThreadPoolExecutor
from math import cos, isfinite, radians
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "frontend/public/circuit-roads"
METRES_PER_DEGREE = 111_195


def download(url):
    with urlopen(url, timeout=25) as response:
        return response.read()


def centreline_csv(data, width_m):
    geometry = json.loads(data)["features"][0]["geometry"]
    coordinates = geometry["coordinates"]
    if geometry["type"] != "LineString" or len(coordinates) < 30:
        raise ValueError("A circuit needs a complete centreline")
    lon0, lat0 = coordinates[0]
    metres_east = METRES_PER_DEGREE * cos(radians(lat0))
    half_width = width_m / 2
    csv = ["# x_m,y_m,width_right_m,width_left_m"]
    for lon, lat in coordinates:
        east, north = (lon - lon0) * metres_east, (lat - lat0) * METRES_PER_DEGREE
        csv.append(f"{east:.6f},{north:.6f},{half_width:.3f},{half_width:.3f}")
    return ("\n".join(csv) + "\n").encode("utf-8")


def validate_csv(contents, path):
    rows = [
        [float(value) for value in line.split(",")]
        for line in contents.decode("utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if len(rows) < 30 or any(
        len(row) != 4 or not all(map(isfinite, row)) or min(row[2:]) <= 0 for row in rows
    ):
        raise ValueError(f"{path} is not a complete four-column road profile")


def main():
    catalog = json.loads((ROOT / "shared/circuit-catalog.json").read_text(encoding="utf-8"))
    sources = catalog["roadSources"]
    centreline_base = sources["f1-circuits"]["downloadBase"]

    def fetch_circuit(circuit):
        circuit_id = circuit["id"]
        centreline = download(f"{centreline_base}{circuit_id}.geojson")
        width_m = circuit.get("estimatedWidthM", catalog["defaultEstimatedWidthM"])
        assets = {ASSETS / "centrelines" / f"{circuit_id}.csv": centreline_csv(centreline, width_m)}
        if profile := circuit.get("widthProfile"):
            file = profile["file"]
            assets[ASSETS / file] = download(sources[profile["source"]]["downloadBase"] + file)
        for path, contents in assets.items():
            validate_csv(contents, path)
        return assets

    # Complete and validate every download before replacing local assets.
    with ThreadPoolExecutor(max_workers=6) as pool:
        assets = list(pool.map(fetch_circuit, catalog["circuits"]))
    for files in assets:
        for path, contents in files.items():
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(contents)
    print(f"Synced {len(assets)} centrelines and {sum(len(files) - 1 for files in assets)} width profiles")


if __name__ == "__main__":
    main()
