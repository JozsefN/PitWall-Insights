"""Disposable PostgreSQL schemas; integration tests never queue work in public."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.config import settings
from modules.ingestion.domain.models import SourceSessionBundle
from modules.normalization.application.service import NormalizationService
from modules.session_domain.domain.models import SessionCatalogItem
from modules.session_domain.infrastructure.repository import SessionRepository
from modules.storage.infrastructure.base import Base
import modules.storage.infrastructure.db  # register all existing models


@contextmanager
def isolated_database():
    schema = "pw_test_" + uuid4().hex
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    scoped = engine.execution_options(schema_translate_map={None: schema})
    Base.metadata.create_all(scoped)
    factory = sessionmaker(bind=scoped, autoflush=False, expire_on_commit=False)
    try:
        yield factory
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()


def source_bundle(full=False):
    date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    laps = [
        {
            "DriverNumber": number,
            "LapNumber": lap,
            "LapStartTime": timedelta(seconds=(lap - 1) * 60),
            "Time": timedelta(seconds=lap * 60),
            "LapTime": timedelta(seconds=60),
            "Stint": 1,
            "Compound": "SOFT",
            "IsAccurate": True,
            "TyreLife": lap,
            "Sector1Time": timedelta(seconds=20),
            "Sector2Time": timedelta(seconds=20),
            "Sector3Time": timedelta(seconds=20),
            "Position": int(number),
        }
        for number in ("1", "2")
        for lap in (1, 2)
    ]
    car = (
        {
            number: [
                {
                    "SessionTime": timedelta(seconds=t),
                    "Date": date + timedelta(seconds=t),
                    "Speed": 200 + t / 10,
                    "Throttle": 100,
                    "Brake": False,
                    "RPM": 10000,
                    "nGear": 6,
                    "DRS": 12,
                }
                for t in range(0, 120)
            ]
            for number in ("1", "2")
        }
        if full
        else {}
    )
    positions = (
        {
            number: [
                {
                    "SessionTime": timedelta(seconds=t),
                    "Date": date + timedelta(seconds=t),
                    "X": t * 10 + 1,
                    "Y": int(number) * 10,
                    "Z": 0,
                    "Status": "OnTrack",
                }
                for t in range(0, 120)
            ]
            for number in ("1", "2")
        }
        if full
        else {}
    )
    return SourceSessionBundle(
        source="fastf1",
        import_profile="full" if full else "core",
        catalog_item=SessionCatalogItem(
            source="fastf1",
            source_event_key="test:event",
            source_session_key="test:session",
            season_year=2025,
            round_number=1,
            event_name="Integration fixture",
            session_name="Race",
        ),
        drivers=[
            {"DriverNumber": n, "Abbreviation": "D" + n, "FullName": "Test " + n}
            for n in ("1", "2")
        ],
        laps=laps,
        car_telemetry=car,
        position_data=positions,
        source_version="fixture-v1",
    )


def seed_session(factory, full=False):
    with factory() as db:
        snapshot = NormalizationService().build_snapshot(
            source_bundle(full), ttl_hours=1
        )
        return SessionRepository(db).import_snapshot(
            snapshot, source_version="fixture-v1", force_refresh=False
        )


class FixtureSource:
    def load_session(self, request, *, telemetry_selection=None):
        bundle = source_bundle(full=True)
        if telemetry_selection:
            bundle.car_telemetry = {
                key: rows
                for key, rows in bundle.car_telemetry.items()
                if key in telemetry_selection.driver_numbers
                and "car" in telemetry_selection.kinds
            }
            bundle.position_data = {
                key: rows
                for key, rows in bundle.position_data.items()
                if key in telemetry_selection.driver_numbers
                and "position" in telemetry_selection.kinds
            }
        return bundle
