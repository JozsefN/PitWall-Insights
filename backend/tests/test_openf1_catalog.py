import builtins
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from modules.ingestion.infrastructure.openf1_catalog import OpenF1Catalog
from modules.ingestion.infrastructure.openf1_adapter import OpenF1Adapter
from modules.ingestion.infrastructure.provider_registry import build_session_source
from modules.session_domain.domain.models import SessionImportRequest
from test_openf1_adapter import RowsClient


class NativeCalendarTests(unittest.TestCase):
    def setUp(self):
        self.client = RowsClient()
        self.client.rows["meetings"] = [{"meeting_key":8,"meeting_name":"Fixture Grand Prix","date_start":"2025-01-01T00:00:00Z"}]
        self.client.rows["sessions"][0].update(session_name="Race",session_type="Race",country_name="Test country",location="Fixture Circuit")

    def test_calendar_has_stable_native_keys_and_only_completed_sessions_can_import(self):
        item = OpenF1Catalog(self.client).list_catalog(2025)[0]
        self.assertEqual(item.source,"openf1")
        self.assertEqual(item.source_session_key,"openf1:session:42")
        self.assertEqual(item.event_name,"Fixture Grand Prix")
        self.assertEqual(item.round_number,1)
        self.assertTrue(item.available_for_import)
        self.client.rows["sessions"][0]["date_end"] = (datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat()
        item = OpenF1Catalog(self.client).list_catalog(2025)[0]
        self.assertFalse(item.available_for_import)
        self.assertIn("30 minutes",item.unavailable_reason)
        self.client.rows["sessions"][0]["is_cancelled"] = True
        self.assertIn("cancelled",OpenF1Catalog(self.client).list_catalog(2025)[0].unavailable_reason)

    def test_calendar_uses_the_venue_country_for_a_relocated_event(self):
        self.client.rows["meetings"][0]["meeting_name"] = "Bahrain Grand Prix"
        session = self.client.rows["sessions"][0]
        session.update(circuit_key=12, country_name="Bahrain", location="Kuala Lumpur")
        catalog = OpenF1Catalog(self.client)
        item = catalog.list_catalog(2025)[0]
        self.assertEqual((item.event_name, item.circuit_key, item.country), ("Bahrain Grand Prix", "12", "Malaysia"))
        session.update(circuit_key=63, location="Sakhir")
        item = catalog.list_catalog(2025)[0]
        self.assertEqual((item.circuit_key, item.country), ("63", "Bahrain"))
        session.update(circuit_key=999)
        item = catalog.list_catalog(2025)[0]
        self.assertEqual((item.circuit_key, item.country), ("999", "Bahrain"))

    def test_native_calendar_import_and_normalization_do_not_import_another_provider(self):
        original = builtins.__import__
        def without_retired_provider(name,*args,**kwargs):
            if name == "fastf1" or name.startswith("fastf1."):
                raise AssertionError("Retired provider imported")
            return original(name,*args,**kwargs)
        with patch("builtins.__import__",side_effect=without_retired_provider):
            adapter=OpenF1Adapter(client=self.client)
            bundle=adapter.load_session(SessionImportRequest(season_year=2025,round_number=1,session_name="Race",source_session_key="openf1:session:42",import_profile="full"))
            from modules.normalization.application.service import NormalizationService
            snapshot=NormalizationService().build_snapshot(bundle,ttl_hours=1)
        self.assertEqual(snapshot.session.source,"openf1")
        self.assertEqual(snapshot.session.data_provider,"openf1")
        self.assertTrue(snapshot.car_samples)
        self.assertTrue(snapshot.position_samples)

    def test_registry_has_one_provider_and_never_silently_switches_sources(self):
        self.assertIsInstance(build_session_source(),OpenF1Adapter)
        for source in ("fastf1","hybrid","f1tv","unknown"):
            with self.subTest(source=source),self.assertRaises(ValueError):
                build_session_source(source)

    def test_unsupported_season_fails_before_network_requests(self):
        with self.assertRaisesRegex(ValueError,"2023"):
            OpenF1Catalog(self.client).list_catalog(2022)
        self.assertEqual(self.client.calls,[])
