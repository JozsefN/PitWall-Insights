from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from modules.ingestion.domain.models import IngestionSourceStatus, SourceSessionBundle, SourceSessionMetadata
from modules.session_domain.domain.models import SessionCatalogItem, SessionImportRequest


class FastF1Adapter:
    source_name = "fastf1"

    def __init__(self, cache_dir: str | None = None) -> None:
        self.cache_dir = Path(cache_dir or settings.fastf1_cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._fastf1 = None

    def get_status(self) -> IngestionSourceStatus:
        try:
            fastf1 = self._load_fastf1()
            version = getattr(fastf1, "__version__", "unknown")
            return IngestionSourceStatus(
                source_name=self.source_name,
                configured=True,
                status=f"ready:{version}",
                cache_dir=str(self.cache_dir),
                import_timeout_seconds=settings.fastf1_import_timeout,
            )
        except Exception as exc:
            return IngestionSourceStatus(
                source_name=self.source_name,
                configured=False,
                status=f"error:{exc}",
                cache_dir=str(self.cache_dir),
                import_timeout_seconds=settings.fastf1_import_timeout,
            )

    def list_catalog(self, season_year: int) -> list[SessionCatalogItem]:
        fastf1 = self._load_fastf1()
        schedule = fastf1.get_event_schedule(season_year)
        catalog_items: list[SessionCatalogItem] = []

        for row in schedule.to_dict(orient="records"):
            event_name = self._as_text(row.get("EventName")) or f"Round {season_year}"
            session_columns = [
                key for key in row.keys() if key.startswith("Session") and key[-1:].isdigit()
            ]
            for key in sorted(session_columns):
                session_name = self._as_text(row.get(key))
                if not session_name:
                    continue

                session_date = row.get(f"{key}DateUtc") or row.get(f"{key}Date")
                session_type = row.get(f"{key}Type")
                round_number = self._as_int(row.get("RoundNumber"))
                session_key = self._build_session_key(
                    season_year=season_year,
                    round_number=round_number,
                    session_name=session_name,
                )

                catalog_items.append(
                    SessionCatalogItem(
                        source=self.source_name,
                        source_event_key=self._build_event_key(
                            season_year=season_year,
                            round_number=round_number,
                            event_name=event_name,
                        ),
                        source_session_key=session_key,
                        season_year=season_year,
                        round_number=round_number,
                        event_name=event_name,
                        official_event_name=self._as_text(row.get("OfficialEventName")),
                        country=self._as_text(row.get("Country")),
                        location=self._as_text(row.get("Location")),
                        event_format=self._as_text(row.get("EventFormat")),
                        is_testing=bool(row.get("EventFormat") == "testing"),
                        session_name=session_name,
                        session_type=self._as_text(session_type),
                        scheduled_start_utc=self._as_datetime(session_date),
                    )
                )

        catalog_items.sort(
            key=lambda item: (
                item.round_number is None,
                item.round_number or 0,
                item.scheduled_start_utc.timestamp() if item.scheduled_start_utc else 0.0,
                item.session_name,
            )
        )
        return catalog_items

    def load_session(self, request: SessionImportRequest) -> SourceSessionBundle:
        fastf1 = self._load_fastf1()
        session = fastf1.get_session(
            request.season_year,
            request.round_number,
            request.session_name,
        )
        session.load(
            laps=True,
            telemetry=True,
            weather=True,
            messages=True,
        )

        event = session.event
        event_name = self._as_text(event.get("EventName")) or f"Round {request.round_number}"
        session_display_name = self._as_text(getattr(session, "name", None)) or request.session_name
        catalog_item = SessionCatalogItem(
            source=self.source_name,
            source_event_key=self._build_event_key(
                season_year=request.season_year,
                round_number=request.round_number,
                event_name=event_name,
            ),
            source_session_key=self._build_session_key(
                season_year=request.season_year,
                round_number=request.round_number,
                session_name=request.session_name,
            ),
            season_year=request.season_year,
            round_number=request.round_number,
            event_name=event_name,
            official_event_name=self._as_text(event.get("OfficialEventName")),
            country=self._as_text(event.get("Country")),
            location=self._as_text(event.get("Location")),
            event_format=self._as_text(event.get("EventFormat")),
            is_testing=bool(event.get("EventFormat") == "testing"),
            session_name=session_display_name,
            session_type=self._as_text(getattr(session, "session_type", None)),
            scheduled_start_utc=self._as_datetime(
                getattr(session, "date", None) or event.get("EventDate")
            ),
        )

        metadata = SourceSessionMetadata(
            meeting_key=self._as_text(getattr(session, "meeting_key", None)),
            session_key=self._as_text(getattr(session, "session_key", None)),
            api_path=self._as_text(getattr(session, "api_path", None)),
            f1_api_support=getattr(session, "f1_api_support", None),
            actual_start_utc=self._as_datetime(getattr(session, "date", None)),
            session_info=self._coerce_mapping(getattr(session, "session_info", None)),
        )

        drivers = self._extract_driver_rows(session)
        results = self._to_records(getattr(session, "results", None))
        laps = self._to_records(getattr(session, "laps", None))
        weather = self._to_records(getattr(session, "weather_data", None))
        session_status = self._to_records(getattr(session, "session_status", None))
        track_status = self._to_records(getattr(session, "track_status", None))
        race_control_messages = self._to_records(getattr(session, "race_control_messages", None))
        car_telemetry = self._extract_telemetry(session, "car_data")
        position_data = self._extract_telemetry(session, "pos_data")

        return SourceSessionBundle(
            source=self.source_name,
            catalog_item=catalog_item,
            metadata=metadata,
            drivers=drivers,
            results=results,
            laps=laps,
            weather=weather,
            session_status=session_status,
            track_status=track_status,
            race_control_messages=race_control_messages,
            car_telemetry=car_telemetry,
            position_data=position_data,
            fastf1_version=self._as_text(getattr(fastf1, "__version__", None)),
        )

    def _load_fastf1(self) -> Any:
        if self._fastf1 is None:
            import fastf1

            fastf1.Cache.enable_cache(str(self.cache_dir))
            self._fastf1 = fastf1
        return self._fastf1

    def _extract_driver_rows(self, session: Any) -> list[dict[str, Any]]:
        driver_rows: list[dict[str, Any]] = []
        seen_driver_numbers: set[str] = set()

        results = getattr(session, "results", None)
        if results is not None:
            for row in self._to_records(results):
                driver_number = self._as_text(row.get("DriverNumber"))
                if not driver_number:
                    continue
                seen_driver_numbers.add(driver_number)
                driver_rows.append(row)

        for driver_number in getattr(session, "drivers", []):
            driver_key = self._as_text(driver_number)
            if not driver_key or driver_key in seen_driver_numbers:
                continue
            try:
                driver_rows.append(self._coerce_mapping(session.get_driver(driver_number)))
            except Exception:
                driver_rows.append({"DriverNumber": driver_key})

        return driver_rows

    def _extract_telemetry(self, session: Any, attr_name: str) -> dict[str, list[dict[str, Any]]]:
        telemetry_by_driver: dict[str, list[dict[str, Any]]] = {}
        session_attr = getattr(session, attr_name, None)

        for driver_number in getattr(session, "drivers", []):
            driver_key = self._as_text(driver_number)
            if not driver_key:
                continue
            try:
                telemetry = None
                if isinstance(session_attr, dict):
                    telemetry = session_attr.get(driver_key)
                elif session_attr is not None and hasattr(session_attr, "__getitem__"):
                    telemetry = session_attr[driver_key]

                if telemetry is None:
                    laps = session.laps.pick_drivers(driver_key)
                    if laps is None or getattr(laps, "empty", False):
                        telemetry_by_driver[driver_key] = []
                        continue
                    getter_name = "get_car_data" if attr_name == "car_data" else "get_pos_data"
                    getter = getattr(laps, getter_name, None)
                    telemetry = getter() if callable(getter) else None

                telemetry_by_driver[driver_key] = self._to_records(telemetry)
            except Exception:
                telemetry_by_driver[driver_key] = []

        return telemetry_by_driver

    @staticmethod
    def _to_records(value: Any) -> list[dict[str, Any]]:
        if value is None:
            return []

        if hasattr(value, "to_dict"):
            try:
                records = value.to_dict(orient="records")
                if isinstance(records, list):
                    return [FastF1Adapter._coerce_mapping(item) for item in records]
            except TypeError:
                pass

        if isinstance(value, list):
            return [FastF1Adapter._coerce_mapping(item) for item in value]

        return []

    @staticmethod
    def _coerce_mapping(value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return dict(value)
        if hasattr(value, "items"):
            try:
                return dict(value.items())
            except Exception:
                return dict(value)
        return {}

    @staticmethod
    def _as_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() in {"nan", "nat", "none"}:
            return None
        return text

    @staticmethod
    def _as_int(value: Any) -> int | None:
        try:
            if value is None or str(value).strip().lower() in {"", "nan", "nat", "none"}:
                return None
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_datetime(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if hasattr(value, "to_pydatetime"):
            try:
                converted = value.to_pydatetime()
                return converted if converted.tzinfo else converted.replace(tzinfo=timezone.utc)
            except Exception:
                return None
        return None

    @staticmethod
    def _build_event_key(season_year: int, round_number: int | None, event_name: str | None) -> str:
        event_fragment = (event_name or "unknown-event").strip().lower().replace(" ", "-")
        return f"fastf1:{season_year}:{round_number or 0}:{event_fragment}"

    @staticmethod
    def _build_session_key(season_year: int, round_number: int | None, session_name: str) -> str:
        session_fragment = session_name.strip().lower().replace(" ", "-")
        return f"fastf1:{season_year}:{round_number or 0}:{session_fragment}"
