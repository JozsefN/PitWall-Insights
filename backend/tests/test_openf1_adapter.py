import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from modules.ingestion.infrastructure.openf1_adapter import OpenF1Adapter
from modules.ingestion.domain.models import TelemetrySelection
from modules.normalization.application.service import NormalizationService
from modules.session_domain.domain.models import SessionCatalogItem, SessionImportRequest


class RowsClient:
    def __init__(self):
        self.calls = []
        self.rows = {
            "sessions": [{"session_key":42,"meeting_key":8,"date_start":"2025-01-01T13:00:00+00:00","date_end":"2025-01-01T15:00:00+00:00"}],
            "drivers": [{"session_key":42,"driver_number":1,"full_name":"Test One","name_acronym":"ONE"}],
            "laps": [{"session_key":42,"driver_number":1,"lap_number":n,"date_start":f"2025-01-01T13:0{n-1}:00+00:00","lap_duration":60,"duration_sector_1":20,"duration_sector_2":20,"duration_sector_3":20} for n in range(1,5)],
            "stints": [{"session_key":42,"driver_number":1,"lap_start":1,"lap_end":4,"stint_number":1,"compound":"SOFT","tyre_age_at_start":0}],
            "weather": [{"session_key":42,"date":"2025-01-01T13:00:00+00:00","wind_speed":10}],
            "race_control": [{"session_key":42,"date":"2025-01-01T12:59:00+00:00","message":"GREEN FLAG","flag":"GREEN","scope":"Track"}], "session_result": [],
            "pit": [], "intervals": [], "position": [], "starting_grid": [], "overtakes": [], "team_radio": [],
            "car_data": [{"session_key":42,"driver_number":1,"date":"2025-01-01T13:00:01+00:00","speed":200,"rpm":10000,"n_gear":6,"throttle":100,"brake":0,"drs":12}],
            "location": [{"session_key":42,"driver_number":1,"date":"2025-01-01T13:00:01+00:00","x":10,"y":20,"z":0}],
        }

    def get(self, resource, **query):
        self.calls.append((resource, query))
        return self.rows[resource]


class OpenF1SourceTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Mock()
        self.catalog.list_catalog.return_value = [SessionCatalogItem(source="openf1", source_event_key="openf1:meeting:8", source_session_key="openf1:session:42",season_year=2025,round_number=1,event_name="Fixture",session_name="Race",scheduled_start_utc=datetime(2025,1,1,13,tzinfo=timezone.utc))]
        self.client = RowsClient()
        self.adapter = OpenF1Adapter(catalog_source=self.catalog, client=self.client)
        self.request = SessionImportRequest(season_year=2025,round_number=1,session_name="Race",import_profile="full")

    def test_both_streams_map_to_existing_contract_with_independent_lap_quality(self):
        bundle = self.adapter.load_session(self.request)
        snapshot = NormalizationService().build_snapshot(bundle, ttl_hours=1)
        self.assertEqual(bundle.metadata.data_provider, "openf1")
        self.assertEqual(snapshot.car_samples[0].speed_kph, 200)
        self.assertFalse(snapshot.car_samples[0].brake_on)
        self.assertEqual(snapshot.position_samples[0].x, 10)
        self.assertEqual(snapshot.weather_samples[0].wind_speed_kph, 36)
        self.assertEqual(snapshot.car_samples[0].session_time_ms, snapshot.position_samples[0].session_time_ms)
        self.assertFalse(snapshot.laps[0].is_accurate)
        self.assertTrue(snapshot.laps[1].is_accurate)
        self.assertEqual(snapshot.session.source_details["quality_policy"], "openf1_clean_lap_v1")
        self.assertEqual(snapshot.laps[0].tyre_life, 1)

    def test_only_selected_stream_and_driver_is_requested(self):
        selected = TelemetrySelection(frozenset({"1"}),frozenset({"car"}))
        bundle = self.adapter.load_session(self.request, telemetry_selection=selected)
        self.assertEqual(bundle.position_data, {})
        self.assertNotIn("location", [resource for resource,_ in self.client.calls])

    def test_session_identity_survives_schedule_changes_and_nearby_sessions(self):
        self.catalog.list_catalog.return_value[0].scheduled_start_utc -= timedelta(hours=4)
        self.client.rows["sessions"].insert(0, {
            "session_key": 43, "meeting_key": 8, "date_start": "2025-01-01T09:30:00+00:00",
        })
        self.adapter.load_session(self.request)
        self.assertEqual(next(query["session_key"] for resource, query in self.client.calls if resource == "drivers"), 42)

    def test_explicit_canonical_origin_is_preserved(self):
        origin = datetime(2025,1,1,12,30,tzinfo=timezone.utc)
        selected = TelemetrySelection(frozenset({"1"}),frozenset({"car"}), clock_origin_utc=origin)
        bundle = self.adapter.load_session(self.request, telemetry_selection=selected)
        self.assertEqual(bundle.car_telemetry["1"][0]["SessionTime"], timedelta(minutes=30,seconds=1))

    def test_legacy_clock_requires_three_consistent_source_anchors(self):
        anchors = tuple(("1", n, (n-1)*60000) for n in (2,3,4))
        selected = TelemetrySelection(frozenset({"1"}),frozenset({"car"}), lap_clock_anchors=anchors)
        bundle = self.adapter.load_session(self.request, telemetry_selection=selected)
        self.assertEqual(bundle.car_telemetry["1"][0]["SessionTime"], timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError,"Cannot align"):
            self.adapter.load_session(self.request, telemetry_selection=TelemetrySelection(frozenset({"1"}),frozenset({"car"}),lap_clock_anchors=anchors[:1]))

    def test_bad_channels_and_missing_stream_do_not_become_successful_telemetry(self):
        self.client.rows["car_data"][0].update(throttle=104,brake=104)
        bundle = self.adapter.load_session(self.request)
        self.assertIsNone(bundle.car_telemetry["1"][0]["Brake"])
        self.assertIsNone(bundle.car_telemetry["1"][0]["Throttle"])
        self.client.rows["location"] = []
        with self.assertRaisesRegex(ValueError,"no position samples"):
            self.adapter.load_session(self.request)

    def test_wrong_session_and_unknown_driver_are_rejected(self):
        self.client.rows["car_data"][0]["session_key"] = 999
        with self.assertRaisesRegex(ValueError,"different session"):
            self.adapter.load_session(self.request)

    def test_optional_endpoint_failure_keeps_replay_but_does_not_certify_clean_pit_status(self):
        original = self.client.get
        def get(resource, **query):
            if resource == "pit":
                raise ValueError("provider outage")
            return original(resource, **query)
        self.client.get = get
        bundle = self.adapter.load_session(self.request)
        self.assertTrue(bundle.car_telemetry["1"])
        self.assertFalse(any(row["IsAccurate"] for row in bundle.laps))
        self.assertIn("pit",bundle.metadata.session_info["unavailable_sources"])

    def test_free_history_and_future_session_gates(self):
        self.request.season_year = 2022
        with self.assertRaisesRegex(ValueError,"starts in 2023"):
            self.adapter.load_session(self.request)
        self.request.season_year = 2025
        self.client.rows["sessions"][0]["date_end"] = (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
        with self.assertRaisesRegex(ValueError,"completed historical"):
            self.adapter.load_session(self.request)

    def test_missing_accuracy_is_not_silently_certified_by_shared_normalizer(self):
        from support import source_bundle
        bundle = source_bundle()
        bundle.laps[0].pop("IsAccurate")
        snapshot = NormalizationService().build_snapshot(bundle,ttl_hours=1)
        self.assertFalse(snapshot.laps[0].is_accurate)
