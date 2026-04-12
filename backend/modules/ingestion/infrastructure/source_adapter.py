from modules.ingestion.domain.models import IngestionSourceStatus, SourceSessionBundle
from modules.ingestion.infrastructure.fastf1_adapter import FastF1Adapter
from modules.session_domain.domain.models import SessionCatalogItem, SessionImportRequest


class IngestionSourceAdapter:
    def __init__(self, fastf1_adapter: FastF1Adapter | None = None) -> None:
        self.fastf1_adapter = fastf1_adapter or FastF1Adapter()

    def get_status(self) -> IngestionSourceStatus:
        return self.fastf1_adapter.get_status()

    def list_catalog(self, season_year: int) -> list[SessionCatalogItem]:
        return self.fastf1_adapter.list_catalog(season_year)

    def load_session(self, request: SessionImportRequest) -> SourceSessionBundle:
        return self.fastf1_adapter.load_session(request)
