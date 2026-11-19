from collections.abc import Callable, Mapping
from modules.ingestion.application.ports import SessionSourcePort
from modules.ingestion.infrastructure.openf1_adapter import OpenF1Adapter


SourceFactory = Callable[..., SessionSourcePort]

_SOURCE_FACTORIES: Mapping[str, SourceFactory] = {
    "openf1": OpenF1Adapter,
}


def build_session_source(source_name: str | None = None, *, db=None, user_id=None, session_id=None) -> SessionSourcePort:
    selected_source = (source_name or "openf1").strip().lower()
    existing = None
    if db is not None and session_id:
        from modules.session_domain.infrastructure.models import EventSessionRecord
        existing = db.get(EventSessionRecord, session_id)
        # Saved OpenF1 sessions from the previous release used a legacy logical source label.
        if existing and existing.data_provider == "openf1":
            selected_source = "openf1"
    factory = _SOURCE_FACTORIES.get(selected_source)
    if factory is None:
        available_sources = ", ".join(sorted(_SOURCE_FACTORIES))
        raise ValueError(
            f"Unsupported ingestion source '{selected_source}'. "
            f"Available sources: {available_sources}"
        )
    return factory(existing_session=existing)
