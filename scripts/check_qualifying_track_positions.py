"""Compare 2025 Q3 positions with independent circuit geometry in metres.

From the repository root, run with backend/.venv/Scripts/python.exe on Windows
or backend/.venv/bin/python on Linux. Downloads are cached in the temp directory.
"""

import argparse
import json
import math
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import urlopen

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import cKDTree


TRACK_REVISION = "e59595d1f3573b30d1ded6a08984935b957688e0"
TRACK_SOURCE = "https://github.com/TUMFTM/racetrack-database"
IMOLA_REVISION = "8094e957b8d6aa8b9f4510c93968556cccd30e02"
IMOLA_SOURCE = f"https://github.com/bacinger/f1-circuits/blob/{IMOLA_REVISION}/circuits/it-1953.geojson"
LOCATION_SOURCE = "https://api.openf1.org/v1/location"
CACHE = Path(tempfile.gettempdir()) / "pitwall-qualifying-audit"
TARGETS = (
    ("Sakhir", 10010, ((81, 14, 89.841), (63, 19, 90.009), (16, 15, 90.175))),
    ("Suzuka", 10002, ((1, 16, 86.983), (4, 14, 86.995), (81, 17, 87.027))),
    ("Silverstone", 9943, ((1, 17, 84.892), (81, 17, 84.995), (4, 19, 85.010))),
    ("Imola", 9983, ((81, 17, 74.670), (1, 16, 74.704), (63, 16, 74.807))),
)
CORNER_WINDOWS = {
    "Sakhir": ("Turn 1", (700, 733, 779)),
    "Suzuka": ("Hairpin", (2870, 2916, 2951)),
    "Silverstone": ("Vale", (5489, 5514, 5560)),
    "Imola": ("Tamburello", (722, 754, 796)),
}
RACE_LAPS = {"Sakhir": (10014, 81, 20), "Suzuka": (10006, 1, 20), "Silverstone": (9947, 4, 47), "Imola": (9987, 81, 58)}


def load_road(circuit):
    if circuit != "Imola":
        path = download(CACHE / f"{circuit}-{TRACK_REVISION[:7]}.csv", f"https://raw.githubusercontent.com/TUMFTM/racetrack-database/{TRACK_REVISION}/tracks/{circuit}.csv")
        return Road(np.loadtxt(path, delimiter=","))
    url = f"https://raw.githubusercontent.com/bacinger/f1-circuits/{IMOLA_REVISION}/circuits/it-1953.geojson"
    feature = json.loads(download(CACHE / "Imola.geojson", url).read_bytes())["features"][0]
    gps = np.asarray(feature["geometry"]["coordinates"])
    metres = (gps - gps[0]) * [111319.49 * math.cos(math.radians(gps[0, 1])), 111131.75]
    # Draw a nominal width from the circuit's published 10–15 m envelope.
    return Road(np.column_stack([metres, np.full((len(metres), 2), 6.25)]))


def download(path, url):
    if not path.exists():
        for attempt in range(4):
            try:
                with urlopen(url, timeout=35) as response:
                    content = response.read()
                path.write_bytes(content)
                if url.startswith("https://api.openf1.org/"):
                    time.sleep(0.7)
                break
            except HTTPError as error:
                if error.code != 429 or attempt == 3:
                    raise
                delay = error.headers.get("Retry-After", "8")
                time.sleep(min(60, max(4, int(delay))) if delay.isdecimal() else 8)
    return path


def hotlaps(circuit, session, specifications):
    metadata = json.loads(download(CACHE / f"{circuit}-laps.json", f"https://api.openf1.org/v1/laps?session_key={session}").read_bytes())
    for driver, number, duration in specifications:
        lap = next(row for row in metadata if row["driver_number"] == driver and row["lap_number"] == number)
        assert abs(lap["lap_duration"] - duration) < 0.001, (circuit, lap)
        points = position_window(lap, CACHE / f"{circuit}-{driver}-location.json")
        yield {"driver": driver, "lap": number, "time_s": duration, "points": points}


def position_window(lap, filename):
    start = datetime.fromisoformat(lap["date_start"])
    end = start + timedelta(seconds=lap["lap_duration"])
    query = urlencode({"session_key": lap["session_key"], "driver_number": lap["driver_number"]})
    window = f"&date%3E={quote(start.isoformat())}&date%3C={quote(end.isoformat())}"
    data = json.loads(download(filename, f"{LOCATION_SOURCE}?{query}{window}").read_bytes())
    assert len(data) >= 150, (lap, len(data))
    assert all(row["driver_number"] == lap["driver_number"] and row["session_key"] == lap["session_key"] for row in data)
    ordered = sorted(data, key=lambda row: datetime.fromisoformat(row["date"]))
    seconds = (datetime.fromisoformat(ordered[-1]["date"]) - datetime.fromisoformat(ordered[0]["date"])).total_seconds()
    assert seconds >= lap["lap_duration"] - 2, (lap, seconds)
    return np.array([(row["x"], row["y"]) for row in ordered], dtype=float) / 10


def check_race_frame(circuit, road, calibration):
    session, driver, number = RACE_LAPS[circuit]
    query = urlencode({"session_key": session, "driver_number": driver, "lap_number": number})
    filename = CACHE / f"{circuit}-race-lap-{number}.json"
    lap, = json.loads(download(filename, f"https://api.openf1.org/v1/laps?{query}").read_bytes())
    points = position_window(lap, CACHE / f"{circuit}-race-positions-{number}.json")
    trace = transform(points, calibration["reflection"], calibration["registration"])
    _, _, _, distance = road.project(trace)
    fraction = float(np.mean(distance <= 18))
    assert fraction >= 0.92, (circuit, fraction)
    return {
        "session_key": session, "driver": driver, "lap": number, "samples": len(points),
        "centre_distance_p95_m": round(float(np.quantile(distance, .95)), 2),
        "within_18m_pct": round(100 * fraction, 1),
    }


class Road:
    def __init__(self, data):
        if np.linalg.norm(data[0, :2] - data[-1, :2]) < 0.1:
            data = data[:-1]
        self.data = data
        self.points = data[:, :2]
        self.end = np.roll(self.points, -1, axis=0)
        self.delta = self.end - self.points
        self.length = np.linalg.norm(self.delta, axis=1)
        assert np.all(self.length > 0)
        self.distance = np.r_[0, np.cumsum(self.length)]
        self.midpoints = cKDTree((self.points + self.end) / 2)

    def project(self, points):
        _, segments = self.midpoints.query(points, k=8)
        delta = self.delta[segments]
        from_start = points[:, None, :] - self.points[segments]
        fraction = np.einsum("ijk,ijk->ij", from_start, delta) / self.length[segments] ** 2
        fraction = np.clip(fraction, 0, 1)
        residual = from_start - delta * fraction[..., None]
        closest = np.argmin(np.einsum("ijk,ijk->ij", residual, residual), axis=1)
        row = np.arange(len(points))
        index = segments[row, closest]
        fraction = fraction[row, closest]
        distance = self.distance[index] + fraction * self.length[index]
        direction = self.delta[index] / self.length[index, None]
        x, y = residual[row, closest].T
        offset = direction[:, 0] * y - direction[:, 1] * x
        widths = self.data[index, 2:] * (1 - fraction[:, None]) + self.data[(index + 1) % len(self.data), 2:] * fraction[:, None]
        return distance, offset, widths, np.hypot(x, y)


def evenly_spaced(points, stride=8):
    distance = np.r_[0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    samples = np.arange(0, distance[-1], stride)
    return np.column_stack([np.interp(samples, distance, axis) for axis in points.T])


def transform(points, reflection, parameters):
    rotation, x, y = parameters
    c, s = math.cos(rotation), math.sin(rotation)
    return (points * [1, reflection]) @ [[c, s], [-s, c]] + [x, y]


def register_road(road, calibration_laps):
    points = np.concatenate([evenly_spaced(lap["points"]) for lap in calibration_laps])
    centre = points.mean(axis=0)
    local = points - centre
    reference = road.points.mean(axis=0)

    def residual(parameters, reflection):
        positioned = transform(local, reflection, parameters)
        _, offset, _, distance = road.project(positioned)
        return np.where(offset < 0, -distance, distance)

    candidates = []
    for reflection in (1, -1):
        for rotation in np.linspace(0, 2 * np.pi, 72, endpoint=False):
            start = [rotation, *reference]
            error = np.quantile(np.abs(residual(start, reflection)), 0.8)
            candidates.append((error, reflection, start))

    best = None
    for _, reflection, start in sorted(candidates)[:8]:
        fit = least_squares(residual, start, args=(reflection,), loss="soft_l1", f_scale=3, x_scale=[0.03, 25, 25])
        if best is None or fit.cost < best[0]:
            best = fit.cost, reflection, fit.x
    _, reflection, parameters = best
    rotation, x, y = parameters
    origin = transform(centre, reflection, (rotation, 0, 0))
    return reflection, (rotation, x - origin[0], y - origin[1])


def evaluate(road, lap, calibration):
    reflection, parameters = register_road(road, calibration)
    trace = transform(lap["points"], reflection, parameters)
    distance, offset, widths, _ = road.project(trace)
    clearance = np.where(offset < 0, widths[:, 0], widths[:, 1]) - np.abs(offset)
    return trace, distance, offset, clearance, {
        "calibration_drivers": [row["driver"] for row in calibration],
        "reflection": reflection,
        "registration": list(parameters),
        "samples": len(trace),
        "left_offset_p95_m": round(float(np.quantile(offset, .95)), 2),
        "right_offset_p95_m": round(float(-np.quantile(offset, .05)), 2),
        "median_edge_clearance_m": round(float(np.median(clearance)), 2),
        "within_2m_of_edge_pct": round(float(100 * np.mean(np.abs(clearance) <= 2)), 1),
        "outside_by_over_2m_pct": round(float(100 * np.mean(clearance < -2)), 1),
    }


def corner_plot(axis, road, trace, distance, offset, clearance, circuit, lap):
    corner, along = CORNER_WINDOWS[circuit]
    indices = np.array([np.argmin(np.abs(distance - value)) for value in along])
    assert np.all(np.diff(indices) > 0)
    lateral = offset[indices]
    assert lateral[0] * lateral[1] < 0 and abs(lateral[0] - lateral[1]) >= 5, (circuit, lateral)
    if circuit != "Imola":
        assert lateral[1] * lateral[2] < 0, (circuit, lateral)

    first = max(0, np.searchsorted(road.distance[:-1], along[0] - 65) - 1)
    last = min(len(road.points), np.searchsorted(road.distance[:-1], along[-1] + 65) + 1)
    road_indices = np.arange(first, last)
    centre = road.points[road_indices]
    normals = np.gradient(centre, axis=0)[:, ::-1] * [-1, 1]
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    left = centre + normals * road.data[road_indices, 3, None]
    right = centre - normals * road.data[road_indices, 2, None]
    surface = np.concatenate([left, right[::-1]])
    axis.fill(*surface.T, color="#dce0e4", zorder=1)
    axis.plot(*left.T, *right.T, color="#667383", linewidth=0.9)
    axis.plot(*centre.T, color="#8c9398", linewidth=0.8, linestyle=(0, (3, 3)))
    section = np.flatnonzero((distance >= along[0] - 30) & (distance <= along[-1] + 30))
    axis.plot(*trace[section].T, color="#1c657e", linewidth=1.8, zorder=3)
    axis.scatter(*trace[section].T, color="#1c657e", s=12, zorder=4)
    axis.scatter(*trace[indices].T, s=55, color="#eb8626", edgecolors="white", linewidths=1, zorder=5)
    for label, index, delta in zip(("In", "Apex", "Out"), indices, ((-7, 9), (7, -11), (7, 9))):
        axis.annotate(label, trace[index], xytext=delta, textcoords="offset points", fontsize=9, fontweight="bold", color="#1d3541", zorder=6)
    axis.set_title(f"{circuit} · {corner} · #{lap['driver']}", loc="left", fontsize=12, fontweight="bold")
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    return {
        "name": corner,
        "offset_m_in_apex_out": np.round(lateral, 2).tolist(),
        "openf1_xy_in_apex_out": np.round(lap["points"][indices] * 10, 2).tolist(),
        "estimated_edge_clearance_at_apex_m": round(float(clearance[indices[1]]), 2),
    }


def main():
    import matplotlib.pyplot as plt

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("docs/testing/replay-map"))
    args = parser.parse_args()
    CACHE.mkdir(exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    report = {"location_source": LOCATION_SOURCE, "geometry_source": TRACK_SOURCE, "geometry_revision": TRACK_REVISION, "imola_geometry_source": IMOLA_SOURCE, "circuits": []}
    figure, axes = plt.subplots(2, 2, figsize=(9.2, 7.5), layout="constrained")
    figure.suptitle("2025 pole laps against independent road geometry", fontweight="bold", fontsize=16)
    for (circuit, session, specs), axis in zip(TARGETS, axes.flat, strict=True):
        road = load_road(circuit)
        pole, *calibration = hotlaps(circuit, session, specs)
        trace, distance, offset, clearance, stats = evaluate(road, pole, calibration)
        assert stats["outside_by_over_2m_pct"] <= 5, (circuit, stats)
        corner = corner_plot(axis, road, trace, distance, offset, clearance, circuit, pole)
        result = {"circuit": circuit, "session_key": session, "driver": pole["driver"], "lap": pole["lap"], "time_s": pole["time_s"], "estimated_nominal_width_m": 12.5 if circuit == "Imola" else None, "corner": corner, **stats,
                  "race_frame_check": check_race_frame(circuit, road, stats)}
        report["circuits"].append(result)
        print(json.dumps(result), flush=True)
    figure.supxlabel("Blue dots show OpenF1 samples. The dashed line is the mapped centreline.\nGeometry by TUMFTM and f1-circuits · © OpenStreetMap contributors · Imola width is estimated.", fontsize=9)
    figure.savefig(args.output / "qualifying-corners.png", dpi=165, facecolor="#fafbfc")
    plt.close(figure)
    (args.output / "qualifying-track-positions.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
