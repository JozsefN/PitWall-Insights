from typing import Protocol

from modules.ingestion.domain.models import SourceSessionBundle
from modules.normalization.domain.models import SessionSnapshot


class SessionSnapshotBuilderPort(Protocol):
    def build(self, bundle: SourceSessionBundle, ttl_hours: int) -> SessionSnapshot: ...
