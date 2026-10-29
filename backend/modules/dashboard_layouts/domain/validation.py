"""Validate persisted layout documents at the API boundary, including grid geometry."""
from copy import deepcopy
from math import isfinite
from typing import Any

import json
from pathlib import Path

# Keep API policy and browser policy in one version-controlled contract.
CATALOG_PATH = Path(__file__).resolve().parents[4] / "shared" / "dashboard-widgets.json"
CATALOG = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
WIDGET_POLICIES = CATALOG["widgets"]
WIDGET_AUDIENCES = {key: set(value["supportedAudiences"]) for key, value in WIDGET_POLICIES.items() if value["builderEnabled"]}


def validate_widget_size(widget_id: str, box: dict) -> None:
    if not isinstance(box, dict) or not all(
        _number(box.get(key), minimum, maximum, True)
        for key, minimum, maximum in (("x", 0, 11), ("y", 0, 199), ("w", 2, 12), ("h", 3, 20))
    ) or box["x"] + box["w"] > 12 or box["y"] + box["h"] > 200:
        raise ValueError("Widget position or size is outside the grid")
    policy = WIDGET_POLICIES[widget_id]
    size = policy["sizing"]
    if not size["minW"] <= box["w"] <= size["maxW"] or not size["minH"] <= box["h"] <= size["maxH"]:
        raise ValueError(f"{policy['title']} requires at least {size['minW']} columns by {size['minH']} rows")
    grid = CATALOG["grid"]
    width = box["w"] * ((grid["designWidth"] + grid["gap"]) / grid["columns"]) - grid["gap"]
    height = box["h"] * (grid["rowHeight"] + grid["gap"]) - grid["gap"]
    aspect = width / height
    if "minAspect" in size and aspect < size["minAspect"]:
        raise ValueError(f"{policy['title']} requires a wider shape")
    if "maxAspect" in size and aspect > size["maxAspect"]:
        raise ValueError(f"{policy['title']} requires a taller shape")


def validate_dashboard_config(config: Any, audience: str = "session-lookback", schema_version: int = 1) -> dict:
    if schema_version not in (1, 2):
        raise ValueError("Unsupported layout schema version")
    if not isinstance(config, dict) or not isinstance(config.get("id"), str) or not config["id"].strip():
        raise ValueError("Layout config requires a string id")
    sections = config.get("sections")
    if not isinstance(sections, list) or not 1 <= len(sections) <= 20:
        raise ValueError("A layout requires between 1 and 20 sections")
    ids: set[str] = set()
    count = [0]
    for section in sections:
        if not isinstance(section, dict) or not isinstance(section.get("id"), str) or not section["id"].strip():
            raise ValueError("Each section requires an id")
        if section["id"] in ids:
            raise ValueError("Section ids must be unique")
        ids.add(section["id"])
        _validate_node(section.get("layout"), audience, schema_version, count, 0)
    if count[0] == 0:
        raise ValueError("Add at least one widget before saving")
    return deepcopy(config)


def _number(value: Any, minimum: float, maximum: float, integer: bool = False) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and minimum <= value <= maximum and isfinite(value) and (not integer or int(value) == value))


def _validate_node(node: Any, audience: str, version: int, count: list[int], depth: int) -> None:
    if depth > 8 or not isinstance(node, dict):
        raise ValueError("Invalid or excessively nested layout node")
    if node.get("type") == "widget":
        count[0] += 1
        if count[0] > 100:
            raise ValueError("A layout supports at most 100 widgets")
        widget_id = node.get("widgetId")
        if not isinstance(widget_id, str) or widget_id not in WIDGET_AUDIENCES:
            raise ValueError("Unknown widget")
        if audience not in WIDGET_AUDIENCES[widget_id]:
            raise ValueError(f"Widget {widget_id} is not available for {audience}")
        if node.get("options") is not None and not isinstance(node["options"], dict):
            raise ValueError("Widget options must be an object")
        options = node.get("options") or {}
        for key in ("title", "metricLabel", "unit"):
            if key in options and (not isinstance(options[key], str) or len(options[key]) > 160):
                raise ValueError(f"Invalid widget {key}")
        if "requiresLap" in options and not isinstance(options["requiresLap"], bool):
            raise ValueError("requiresLap must be a boolean")
        if "metric" in options and options["metric"] not in ("speed_kph", "throttle_pct"):
            raise ValueError("Unknown telemetry metric")
        if version == 2 and node.get("placement") is not None:
            validate_widget_size(widget_id, node["placement"])
        for key in ("minHeight", "maxHeight"):
            if key in node and not _number(node[key], 0, 10000):
                raise ValueError(f"Invalid {key}")
        return
    if node.get("type") != "group" or node.get("direction") not in ("row", "column"):
        raise ValueError("Invalid layout group")
    children = node.get("children")
    if not isinstance(children, list) or not children:
        raise ValueError("A group requires widgets")
    if "gap" in node and not _number(node["gap"], 0, 100):
        raise ValueError("Invalid group gap")
    if node.get("grid") is not None:
        grid = node["grid"]
        if version != 2 or not isinstance(grid, dict) or grid.get("columns") != 12 or grid.get("rowHeight") != 48:
            raise ValueError("Grid layouts require schema version 2 and a 12-column, 48-pixel grid")
        placed = []
        instance_ids = set()
        for child in children:
            if not isinstance(child, dict) or child.get("type") != "widget":
                raise ValueError("Grid children must be widgets")
            key = child.get("instanceId")
            if not isinstance(key, str) or not key or key in instance_ids:
                raise ValueError("Grid widget instance ids must be unique")
            instance_ids.add(key)
            box = child.get("placement")
            if not isinstance(box, dict) or not all(
                _number(box.get(k), lo, hi, True)
                for k, lo, hi in (("x", 0, 11), ("y", 0, 199), ("w", 2, 12), ("h", 3, 20))
            ) or box["x"] + box["w"] > 12 or box["y"] + box["h"] > 200:
                raise ValueError("Widget position or size is outside the grid")
            for other in placed:
                if (box["x"] < other["x"] + other["w"] and box["x"] + box["w"] > other["x"]
                        and box["y"] < other["y"] + other["h"] and box["y"] + box["h"] > other["y"]):
                    raise ValueError("Grid widgets must not overlap")
            placed.append(box)
    for child in children:
        _validate_node(child, audience, version, count, depth + 1)
