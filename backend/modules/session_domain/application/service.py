from datetime import datetime, timezone

from app.config import settings
from modules.ingestion.application.service import IngestionService
from modules.normalization.application.service import NormalizationService
from modules.session_domain.domain.models import (
    CarTelemetrySampleModel,
    EntryLapModel,
    PositionSampleModel,
    SessionCatalogItem,
    SessionDetail,
    SessionEntrySummary,
    SessionImportRequest,
    SessionSummary,
    SessionTickModel,
)
from modules.session_domain.infrastructure.repository import SessionRepository


class SessionService:
    def __init__(
        self,
        repository: SessionRepository,
        ingestion_service: IngestionService,
        normalization_service: NormalizationService,
    ) -> None:
        self.repository = repository
        self.ingestion_service = ingestion_service
        self.normalization_service = normalization_service

    def list_catalog(self, season_year: int) -> list[SessionCatalogItem]:
        return self.ingestion_service.list_catalog(season_year)

    def import_session(self, request: SessionImportRequest) -> SessionDetail:
        started_at = datetime.now(timezone.utc)
        bundle = self.ingestion_service.load_session(request)
        snapshot = self.normalization_service.build_snapshot(
            bundle=bundle,
            ttl_hours=settings.session_cache_ttl_hours,
        )
        session_id = self.repository.import_snapshot(
            snapshot,
            source_version=bundle.source_version,
            force_refresh=request.force_refresh,
            started_at=started_at,
        )
        session = self.get_session(session_id)
        if session is None:
            raise ValueError("Imported session could not be loaded")
        return session

    def delete_session(self, session_id: str) -> bool:
        return self.repository.delete_session(session_id)

    def list_sessions(self) -> list[SessionSummary]:
        return self.repository.list_sessions()

    def get_session(self, session_id: str) -> SessionDetail | None:
        return self.repository.get_session(session_id)

    def list_entries(self, session_id: str) -> list[SessionEntrySummary]:
        return self.repository.list_entries(session_id)

    def list_entry_laps(self, session_id: str, entry_id: str) -> list[EntryLapModel]:
        return self.repository.list_entry_laps(session_id, entry_id)

    def list_car_telemetry(
        self,
        session_id: str,
        entry_id: str,
        *,
        offset: int,
        limit: int,
        lap_number: int | None = None,
        session_time_from_ms: int | None = None,
        session_time_to_ms: int | None = None,
    ) -> list[CarTelemetrySampleModel]:
        return self.repository.list_car_telemetry(
            session_id,
            entry_id,
            offset=offset,
            limit=limit,
            lap_number=lap_number,
            session_time_from_ms=session_time_from_ms,
            session_time_to_ms=session_time_to_ms,
        )

    def list_position_telemetry(
        self,
        session_id: str,
        entry_id: str,
        *,
        offset: int,
        limit: int,
        lap_number: int | None = None,
        session_time_from_ms: int | None = None,
        session_time_to_ms: int | None = None,
    ) -> list[PositionSampleModel]:
        return self.repository.list_position_telemetry(
            session_id,
            entry_id,
            offset=offset,
            limit=limit,
            lap_number=lap_number,
            session_time_from_ms=session_time_from_ms,
            session_time_to_ms=session_time_to_ms,
        )

    def list_ticks(
        self,
        session_id: str,
        *,
        offset: int,
        limit: int,
    ) -> list[SessionTickModel]:
        return self.repository.list_ticks(session_id, offset=offset, limit=limit)
