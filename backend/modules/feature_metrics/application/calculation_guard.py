"""One bounded compute slot shared by analytics and strategy; source workers stay independent."""

from threading import BoundedSemaphore
from sqlalchemy import select, func

_ANALYSIS_GATE = BoundedSemaphore(1)


class AnalysisBusyError(RuntimeError):
    pass


class AnalysisChangedError(RuntimeError):
    pass


def acquire_database_lock(db):
    schema = (
        db.get_bind().get_execution_options().get("schema_translate_map", {}).get(None)
    )
    scope = schema if schema is not None else func.current_schema()
    return bool(
        db.scalar(
            select(
                func.pg_try_advisory_xact_lock(
                    func.hashtextextended(func.concat("pitwall:analysis:", scope), 0)
                )
            )
        )
    )
