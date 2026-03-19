from modules.ingestion.domain.models import IngestionSourceStatus
from modules.ingestion.infrastructure.source_adapter import IngestionSourceAdapter


class IngestionService:
    def __init__(self, source_adapter: IngestionSourceAdapter) -> None:
        self.source_adapter = source_adapter

    def get_status(self) -> IngestionSourceStatus:
        return self.source_adapter.get_status()