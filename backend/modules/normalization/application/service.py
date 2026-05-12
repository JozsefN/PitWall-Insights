from collections.abc import Callable

from modules.ingestion.domain.models import SourceSessionBundle
from modules.normalization.application.builder_registry import build_snapshot_builder
from modules.normalization.application.ports import SessionSnapshotBuilderPort
from modules.normalization.domain.models import NormalizationStatus, SessionSnapshot


SnapshotBuilderFactory = Callable[[str], SessionSnapshotBuilderPort]


class NormalizationService:
    def __init__(self, builder_factory: SnapshotBuilderFactory | None = None) -> None:
        self.builder_factory = builder_factory or build_snapshot_builder

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
        builder = self.builder_factory(bundle.source)
        return builder.build(bundle=bundle, ttl_hours=ttl_hours)
