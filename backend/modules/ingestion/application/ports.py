from typing import Protocol

from modules.ingestion.domain.models import IngestionSourceStatus, SourceSessionBundle
from modules.session_domain.domain.models import (
    SessionCatalogItem,
    SessionCircuitCornerModel,
    SessionImportRequest,
)


class SessionSourcePort(Protocol):
    def get_status(self) -> IngestionSourceStatus: ...
    def list_catalog(self, season_year: int) -> list[SessionCatalogItem]: ...
    def load_session(self, request: SessionImportRequest) -> SourceSessionBundle: ...
    def list_circuit_corners(self, request: SessionImportRequest) -> list[SessionCircuitCornerModel]: ...
