from collections.abc import Callable, Mapping

from modules.normalization.application.ports import SessionSnapshotBuilderPort
from modules.normalization.application.session_snapshot_builder import FastF1SessionSnapshotBuilder


SnapshotBuilderFactory = Callable[[], SessionSnapshotBuilderPort]

_SNAPSHOT_BUILDER_FACTORIES: Mapping[str, SnapshotBuilderFactory] = {
    FastF1SessionSnapshotBuilder.source_name: FastF1SessionSnapshotBuilder,
}


def build_snapshot_builder(source: str) -> SessionSnapshotBuilderPort:
    selected_source = source.strip().lower()
    factory = _SNAPSHOT_BUILDER_FACTORIES.get(selected_source)
    if factory is None:
        available_sources = ", ".join(sorted(_SNAPSHOT_BUILDER_FACTORIES))
        raise ValueError(
            f"Unsupported normalization source '{selected_source}'. "
            f"Available sources: {available_sources}"
        )
    return factory()
