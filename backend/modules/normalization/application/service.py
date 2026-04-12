from modules.ingestion.domain.models import SourceSessionBundle
from modules.normalization.application.session_snapshot_builder import SessionSnapshotBuilder
from modules.normalization.domain.models import NormalizationStatus, SessionSnapshot


class NormalizationService:
    def __init__(self, snapshot_builder: SessionSnapshotBuilder | None = None) -> None:
        self.snapshot_builder = snapshot_builder or SessionSnapshotBuilder()

    def get_status(self) -> NormalizationStatus:
        return NormalizationStatus(
            pipeline_name="session_normalization",
            status="ready",
            canonical_schema_ready=True,
        )

    def build_snapshot(
        self,
        bundle: SourceSessionBundle,
        ttl_hours: int,
    ) -> SessionSnapshot:
        return self.snapshot_builder.build(bundle=bundle, ttl_hours=ttl_hours)
