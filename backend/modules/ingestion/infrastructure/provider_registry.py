from collections.abc import Callable, Mapping

from app.config import settings
from modules.ingestion.application.ports import SessionSourcePort
from modules.ingestion.infrastructure.fastf1_adapter import FastF1Adapter


SourceFactory = Callable[[], SessionSourcePort]

_SOURCE_FACTORIES: Mapping[str, SourceFactory] = {
    FastF1Adapter.source_name: FastF1Adapter,
}


def build_session_source(source_name: str | None = None) -> SessionSourcePort:
    selected_source = (source_name or settings.ingestion_source).strip().lower()
    factory = _SOURCE_FACTORIES.get(selected_source)
    if factory is None:
        available_sources = ", ".join(sorted(_SOURCE_FACTORIES))
        raise ValueError(
            f"Unsupported ingestion source '{selected_source}'. "
            f"Available sources: {available_sources}"
        )
    return factory()
