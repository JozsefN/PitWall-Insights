"""Fill missing OpenF1 radio without reimporting a session or its telemetry."""

from sqlalchemy.orm import Session

from modules.ingestion.infrastructure.openf1_client import OpenF1Client
from modules.session_domain.infrastructure.models import EventSessionRecord


def _needs_radio(session):
    details = session.source_details or {}
    return "team_radio" not in details or "team_radio" in details.get("unavailable_sources", [])


def recover_openf1_radio(db: Session, session_id: str):
    session = db.get(EventSessionRecord, session_id)
    if session is None or session.deleted_at is not None:
        raise LookupError("Session not found")
    if (
        (session.data_provider or session.source) != "openf1"
        or not (session.session_key or "").isdigit()
        or not _needs_radio(session)
    ):
        return
    key = session.session_key

    # Release the read transaction before waiting on the upstream provider.
    db.rollback()
    rows = OpenF1Client(max_attempts=2, max_retry_wait_seconds=5).get(
        "team_radio", session_key=key
    )

    session = db.get(EventSessionRecord, session_id, populate_existing=True, with_for_update=True)
    if session is None or session.deleted_at is not None or session.session_key != key:
        raise LookupError("Session not found")
    if _needs_radio(session):
        details = dict(session.source_details or {})
        details["team_radio"] = rows
        details["unavailable_sources"] = [
            resource for resource in details.get("unavailable_sources", []) if resource != "team_radio"
        ]
        session.source_details = details
    db.commit()
