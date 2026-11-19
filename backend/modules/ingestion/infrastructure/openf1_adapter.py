"""Historical OpenF1 adapter using the provider's own calendar and telemetry."""
from bisect import bisect_right
from datetime import datetime, timedelta, timezone
import math
import statistics
from modules.ingestion.domain.models import SourceSessionBundle, SourceSessionMetadata, IngestionSourceStatus
from modules.session_domain.domain.models import SessionCatalogItem
from modules.ingestion.infrastructure.openf1_client import OpenF1Client
from modules.normalization.domain.openf1_quality import qualify_laps, QUALITY_POLICY


def utc(value):
    stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("OpenF1 timestamps must include timezone")
    return stamp.astimezone(timezone.utc)


class OpenF1Adapter:
    source_name = "openf1"

    def __init__(self, *, catalog_source=None, client=None, existing_session=None):
        self.client = client or OpenF1Client()
        from .openf1_catalog import OpenF1Catalog
        self.catalog_source = catalog_source or OpenF1Catalog(self.client)
        self.existing_session = existing_session

    def get_status(self):
        cache = getattr(self.client, "cache", None)
        return IngestionSourceStatus(source_name="openf1", configured=True, status="historical",
            cache_dir=str(cache) if cache else None,
            cache_size_bytes=sum(p.stat().st_size for p in cache.glob("*.json.gz")) if cache else None,
            import_timeout_seconds=180)

    def list_catalog(self, season_year):
        return self.catalog_source.list_catalog(season_year)

    def list_circuit_corners(self, request):
        return []  # The replay map is drawn from observed positions.

    def load_session(self, request, *, telemetry_selection=None):
        if request.season_year < 2023:
            raise ValueError("OpenF1 history starts in 2023. Choose a supported season.")
        if self.existing_session and self.existing_session.data_provider not in (None, "openf1"):
            raise ValueError("This session uses a retired source. Open the race again from Sessions to load OpenF1 history.")
        key = request.source_session_key or ""
        if self.existing_session and self.existing_session.data_provider == "openf1" and self.existing_session.session_key:
            # Existing OpenF1 imports keep their saved clock/identity during materialization.
            saved = self.existing_session
            session_rows = self.client.get("sessions", session_key=int(saved.session_key))
            catalog = SessionCatalogItem(source="openf1", source_event_key=saved.weekend.source_event_key,
                source_session_key=saved.source_session_key, season_year=request.season_year,
                round_number=saved.weekend.round_number, event_name=saved.weekend.event_name,
                country=saved.weekend.country, location=saved.weekend.location,
                session_name=saved.session_name, session_type=saved.session_type,
                scheduled_start_utc=saved.scheduled_start_utc)
        else:
            catalog = None
            session_rows = None
        candidates = [] if catalog else [item for item in self.catalog_source.list_catalog(request.season_year)
                      if (item.source_session_key == key if key else item.round_number == request.round_number and item.session_name.lower() == request.session_name.lower())]
        if catalog is None and len(candidates) != 1:
            raise ValueError("The requested session could not be matched to the season catalogue")
        catalog = catalog or candidates[0]
        sessions = session_rows if session_rows is not None else self.client.get("sessions", year=request.season_year, session_name=catalog.session_name)
        matches = [
            row for row in sessions
            if f"openf1:session:{row.get('session_key')}" == catalog.source_session_key
        ]
        if len(matches) != 1 or matches[0].get("is_cancelled"):
            raise ValueError("OpenF1 session identity is unavailable or ambiguous")
        session = matches[0]
        if utc(session["date_end"])+timedelta(minutes=30) >= datetime.now(timezone.utc):
            raise ValueError("OpenF1 supports completed historical sessions here. Try again 30 minutes after this session ends.")
        sid = session["session_key"]
        def get(resource, **query):
            rows = self.client.get(resource, session_key=sid, refresh=request.force_refresh, **query)
            if any(row.get("session_key") != sid for row in rows):
                raise ValueError("OpenF1 returned rows from a different session")
            return rows
        drivers = get("drivers")
        laps = get("laps")
        if not drivers or not laps:
            raise ValueError("OpenF1 returned no usable drivers or laps; this session is incomplete")
        origin = telemetry_selection.clock_origin_utc if telemetry_selection else None
        if origin is None and telemetry_selection and telemetry_selection.lap_clock_anchors:
            lookup = {(str(row["driver_number"]), int(row["lap_number"])): row for row in laps}
            offsets = [(utc(lookup[(car, lap)]["date_start"])-timedelta(milliseconds=start)).timestamp()
                       for car, lap, start in telemetry_selection.lap_clock_anchors
                       if (car, lap) in lookup and lookup[(car, lap)].get("date_start") and lap > 1]
            if len(offsets) < 3:
                raise ValueError("Cannot align the legacy session clock with OpenF1. Import this race again using the free provider.")
            center = statistics.median(offsets)
            inliers = [v for v in offsets if abs(v-center) <= .5]
            if len(inliers) < max(3, math.ceil(.8*len(offsets))):
                raise ValueError("Source clocks disagree; replay data was not mixed. Reimport this race with one provider.")
            origin = datetime.fromtimestamp(statistics.median(inliers), timezone.utc)
        origin = origin or utc(session["date_start"])-timedelta(hours=2)
        def elapsed(stamp):
            return utc(stamp)-origin
        unavailable = []
        def optional(resource):
            try:
                return get(resource)
            except ValueError:
                unavailable.append(resource)
                return []
        stints = optional("stints")
        weather = optional("weather")
        controls = optional("race_control")
        results = optional("session_result")
        pits = optional("pit")
        intervals = optional("intervals") if catalog.session_name in ("Race", "Sprint") else []
        ranks = optional("position")
        grid = optional("starting_grid") if catalog.session_name in ("Race", "Sprint") else []
        overtakes = optional("overtakes") if catalog.session_name in ("Race", "Sprint") else []
        # Media and qualifying annotations belong to the core snapshot. A telemetry
        # materialization job does not need to fetch radio metadata again.
        radio = optional("team_radio") if telemetry_selection is None else []
        is_qualifying = "qualifying" in catalog.session_name.lower() or "shootout" in catalog.session_name.lower()
        qualifying_results = {}
        if is_qualifying:
            for row in results:
                durations = row.get("duration")
                if isinstance(durations, list):
                    qualifying_results[str(row["driver_number"])] = durations[:3]
        converted_laps = []
        for row in laps:
            if not row.get("date_start") or row.get("lap_number") is None:
                continue
            start = elapsed(row["date_start"])
            duration = timedelta(seconds=row["lap_duration"]) if row.get("lap_duration") is not None else None
            stint = next((v for v in stints if v["driver_number"] == row["driver_number"] and v.get("lap_start") is not None and v["lap_start"] <= row["lap_number"] <= (v.get("lap_end") or 1000)), {})
            value = {"DriverNumber": str(row["driver_number"]), "LapNumber": row["lap_number"],
                     "LapStartTime": start, "Time": start+duration if duration else None,
                     "LapTime": duration, "Stint": stint.get("stint_number"), "Compound": stint.get("compound"),
                     "TyreLife": (stint["tyre_age_at_start"]+row["lap_number"]-stint["lap_start"]+1) if stint.get("tyre_age_at_start") is not None else None,
                     # An unknown quality/deletion/track-status value is never certified clean.
                     "IsAccurate": False, "FastF1Generated": False,
                     "OpenF1PitOutLap": row.get("is_pit_out_lap", False),
                     "SpeedI1": row.get("i1_speed"), "SpeedI2": row.get("i2_speed"), "SpeedST": row.get("st_speed")}
            total = start
            for n in (1, 2, 3):
                sector = row.get(f"duration_sector_{n}")
                value[f"Sector{n}Time"] = timedelta(seconds=sector) if sector is not None else None
                total = total+timedelta(seconds=sector) if total is not None and sector is not None else None
                value[f"Sector{n}SessionTime"] = total
            converted_laps.append(value)
        converted_controls = [{"SessionTime": elapsed(row["date"]), "Date": utc(row["date"]),
                               **{name: row.get(source) for name, source in (("Message", "message"), ("Category", "category"), ("Flag", "flag"), ("Scope", "scope"), ("Sector", "sector"), ("Lap", "lap_number"), ("RacingNumber", "driver_number"))}}
                              for row in controls if row.get("date")]
        track_status, lap_quality = qualify_laps(converted_laps, converted_controls, pits)
        if "pit" in unavailable:
            for row in converted_laps:
                row["IsAccurate"] = False
            for item in lap_quality:
                item["clean"] = False
                item["reasons"].append("pit_source_unavailable")
        # Position is race rank, location is XYZ. Use only ranks published by lap end.
        ranks_by_car = {}
        for row in ranks:
            if row.get("date") and row.get("position") is not None:
                ranks_by_car.setdefault(str(row["driver_number"]), []).append((elapsed(row["date"]), row["position"]))
        for values in ranks_by_car.values():
            values.sort()
        for row in converted_laps:
            values = ranks_by_car.get(row["DriverNumber"], [])
            at = bisect_right([v[0] for v in values], row["Time"])-1 if row.get("Time") is not None else -1
            row["Position"] = values[at][1] if at >= 0 else None
        session_status = []
        for row in converted_controls:
            message = (row.get("Message") or "").upper()
            state = "Finished" if row.get("Flag") == "CHEQUERED" or message == "CHEQUERED FLAG" else "Suspended" if row.get("Flag") == "RED" and row.get("Scope") == "Track" else "Started" if row.get("Flag") == "GREEN" and row.get("Scope") == "Track" else None
            if state:
                session_status.append({"SessionTime": row["SessionTime"], "Date": row["Date"], "Status": state})
        details = {"quality_policy": QUALITY_POLICY, "lap_quality": lap_quality,
            "clean_lap_count": sum(v["clean"] for v in lap_quality),
            "lap_timing_note": "Lap starts and derived sector crossing clocks are approximate. Clean means this policy passed, not FastF1 equivalence.",
            "pit_stops": pits, "intervals": intervals, "race_positions": ranks, "starting_grid": grid,
            "classified_gaps": {str(row["driver_number"]): row.get("gap_to_leader") for row in results},
            "pit_out_laps": [{"driver_number": str(row["driver_number"]), "lap_number": row["lap_number"]}
                             for row in laps if row.get("is_pit_out_lap") is True and row.get("lap_number") is not None],
            "overtakes": overtakes, "unavailable_sources": unavailable,
            "circuit_key": session.get("circuit_key"),
            "session_end_utc": session.get("date_end"),
            "session_gmt_offset": session.get("gmt_offset"),
            "driver_headshots": {str(row["driver_number"]): row.get("headshot_url") for row in drivers},
            "team_radio": radio,
            "qualifying_times": qualifying_results,
            "qualifying_segments": [
                {"driver_number": str(row["driver_number"]), "lap_number": row["lap_number"],
                 "sectors": [row.get(f"segments_sector_{n}") for n in (1, 2, 3)]}
                for row in laps if is_qualifying and row.get("lap_number") is not None
            ],
            "coverage": {str(row["driver_number"]): {"expected_laps": row.get("number_of_laps"),
                "available_laps": sum(v["DriverNumber"] == str(row["driver_number"]) and v.get("LapTime") is not None for v in converted_laps),
                "source_lap_records": sum(v["DriverNumber"] == str(row["driver_number"]) for v in converted_laps)} for row in results}}
        participants = [{"DriverNumber": str(row["driver_number"]), "Abbreviation": row.get("name_acronym"),
                         "FullName": row.get("full_name"), "FirstName": row.get("first_name"), "LastName": row.get("last_name"),
                         "TeamName": row.get("team_name"), "TeamColor": row.get("team_colour")} for row in drivers]
        available = {row["DriverNumber"] for row in participants}
        kinds = telemetry_selection.kinds if telemetry_selection else frozenset({"car", "position"})
        numbers = telemetry_selection.driver_numbers if telemetry_selection else available
        if not numbers <= available:
            raise ValueError("Selected driver is absent from the OpenF1 session roster")
        cars, positions = {}, {}
        if request.import_profile == "full":
            for kind, resource, output in (("car", "car_data", cars), ("position", "location", positions)):
                if kind not in kinds:
                    continue
                for number in sorted(numbers):
                    rows = get(resource, driver_number=number)
                    mapped = []
                    for row in rows:
                        if str(row.get("driver_number")) != number:
                            raise ValueError("OpenF1 telemetry contains an unexpected driver")
                        stamp = elapsed(row["date"])
                        if stamp < timedelta(0):
                            continue
                        value = {"SessionTime": stamp, "Date": utc(row["date"]), "Source": "openf1"}
                        if kind == "car":
                            value.update({dest: row.get(src) for dest, src in (("Speed", "speed"), ("RPM", "rpm"), ("nGear", "n_gear"), ("Throttle", "throttle"), ("DRS", "drs"))})
                            value["Brake"] = bool(row["brake"]) if row.get("brake") in (0, 100) else None
                            if value["Throttle"] is not None and not 0 <= value["Throttle"] <= 100:
                                value["Throttle"] = None
                        else:
                            value.update({dest: row.get(src) for dest, src in (("X", "x"), ("Y", "y"), ("Z", "z"))})
                        mapped.append(value)
                    output[number] = mapped
                if not any(output.values()):
                    raise ValueError(f"OpenF1 has no {kind} samples for these drivers; replay coverage is unavailable")
        return SourceSessionBundle(source="openf1", catalog_item=catalog, import_profile=request.import_profile,
            metadata=SourceSessionMetadata(data_provider="openf1", session_key=str(sid), meeting_key=str(session["meeting_key"]),
                actual_start_utc=utc(session["date_start"]), session_time_origin_utc=origin,
                session_info=details),
            drivers=participants, results=[{"DriverNumber": str(v["driver_number"]), "Position": v.get("position"), "GridPosition": next((g.get("position") for g in grid if g.get("driver_number") == v["driver_number"]), None), "Points": v.get("points"), "Laps": v.get("number_of_laps"),
                **{f"Q{i}": timedelta(seconds=t) for i, t in enumerate(qualifying_results.get(str(v["driver_number"]), []), 1) if isinstance(t, (int, float)) and math.isfinite(t) and t > 0},
                "Status": "Disqualified" if v.get("dsq") else "Did not start" if v.get("dns") else "Retired" if v.get("dnf") else "Finished"} for v in results],
            laps=converted_laps, car_telemetry=cars, position_data=positions,
            weather=[{"SessionTime": elapsed(v["date"]), "Date": utc(v["date"]), **{dest: v.get(src) for dest, src in (("AirTemp", "air_temperature"), ("TrackTemp", "track_temperature"), ("Humidity", "humidity"), ("Pressure", "pressure"), ("Rainfall", "rainfall"), ("WindDirection", "wind_direction"), ("WindSpeed", "wind_speed"))}} for v in weather],
            race_control_messages=converted_controls, track_status=track_status, session_status=session_status, source_version="openf1:v1:"+QUALITY_POLICY)
