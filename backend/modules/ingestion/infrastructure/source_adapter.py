from modules.ingestion.domain.models import IngestionSourceStatus


class IngestionSourceAdapter:
    def get_status(self) -> IngestionSourceStatus:
        return IngestionSourceStatus(
            source_name="mock_source",
            configured=False,
            status="stub",
        )