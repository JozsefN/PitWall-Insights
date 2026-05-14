from modules.ingestion.domain.models import IngestionSourceStatus, SourceSessionBundle
from modules.ingestion.application.ports import SessionSourcePort
from modules.session_domain.domain.models import (
    SessionCatalogItem,
    SessionCircuitCornerModel,
    SessionImportRequest,
)


class IngestionService:
    def __init__(self, source: SessionSourcePort) -> None:
        self.source = source

    def get_status(self) -> IngestionSourceStatus:
        return self.source.get_status()

    def list_catalog(self, season_year: int) -> list[SessionCatalogItem]:
        return self.source.list_catalog(season_year)

    def load_session(self, request: SessionImportRequest) -> SourceSessionBundle:
        return self.source.load_session(request)

    def list_circuit_corners(self, request: SessionImportRequest) -> list[SessionCircuitCornerModel]:
        return self.source.list_circuit_corners(request)
