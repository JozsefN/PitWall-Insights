from modules.ingestion.application.ports import SessionSourcePort
from modules.ingestion.domain.models import IngestionSourceStatus, SourceSessionBundle
from modules.ingestion.infrastructure.provider_registry import build_session_source
from modules.session_domain.domain.models import SessionCatalogItem, SessionImportRequest


class IngestionSourceAdapter:
    def __init__(
        self,
        source: SessionSourcePort | None = None,
        source_name: str | None = None,
    ) -> None:
        self.source = source or build_session_source(source_name)

    def get_status(self) -> IngestionSourceStatus:
        return self.source.get_status()

    def list_catalog(self, season_year: int) -> list[SessionCatalogItem]:
        return self.source.list_catalog(season_year)

    def load_session(self, request: SessionImportRequest) -> SourceSessionBundle:
        return self.source.load_session(request)
