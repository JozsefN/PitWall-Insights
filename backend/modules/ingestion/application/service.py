from modules.ingestion.domain.models import IngestionSourceStatus, SourceSessionBundle
from modules.ingestion.infrastructure.source_adapter import IngestionSourceAdapter
from modules.session_domain.domain.models import SessionCatalogItem, SessionImportRequest


class IngestionService:
    def __init__(self, source_adapter: IngestionSourceAdapter) -> None:
        self.source_adapter = source_adapter

    def get_status(self) -> IngestionSourceStatus:
        return self.source_adapter.get_status()

    def list_catalog(self, season_year: int) -> list[SessionCatalogItem]:
        return self.source_adapter.list_catalog(season_year)

    def load_session(self, request: SessionImportRequest) -> SourceSessionBundle:
        return self.source_adapter.load_session(request)
