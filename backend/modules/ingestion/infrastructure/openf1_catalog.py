"""OpenF1-native calendar and stable provider keys; no authenticated catalogue dependency."""
from datetime import datetime, timedelta, timezone

from modules.session_domain.domain.circuit_catalog import openf1_host_country
from modules.session_domain.domain.models import SessionCatalogItem


class OpenF1Catalog:
    def __init__(self, client):
        self.client = client

    def list_catalog(self, season_year):
        if season_year < 2023:
            raise ValueError("OpenF1 historical sessions start in 2023. Choose a supported season.")
        meetings = self.client.get("meetings", year=season_year, cache_ttl_seconds=300)
        sessions = self.client.get("sessions", year=season_year, cache_ttl_seconds=300)
        by_meeting = {row["meeting_key"]: row for row in meetings}
        race_meetings = sorted({row["meeting_key"] for row in sessions if row.get("session_name") == "Race"},
                               key=lambda key: by_meeting.get(key, {}).get("date_start", ""))
        rounds = {key: n + 1 for n, key in enumerate(race_meetings)}
        now = datetime.now(timezone.utc)
        output = []
        for row in sessions:
            if not row.get("session_key") or not row.get("date_start") or not row.get("session_name"):
                continue
            meeting = by_meeting.get(row["meeting_key"], {})
            def stamp(value):
                return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
            start, end = stamp(row["date_start"]), stamp(row.get("date_end"))
            cancelled = bool(row.get("is_cancelled") or meeting.get("is_cancelled"))
            available = not cancelled and bool(end and end + timedelta(minutes=30) < now)
            reason = None if available else "This session was cancelled." if cancelled else "Available as history 30 minutes after the session ends."
            testing = "test" in (meeting.get("meeting_name", "") + " " + row.get("session_type", "")).lower()
            circuit_key = row.get("circuit_key") or meeting.get("circuit_key")
            output.append(SessionCatalogItem(
                source="openf1", source_event_key=f"openf1:meeting:{row['meeting_key']}",
                source_session_key=f"openf1:session:{row['session_key']}", season_year=season_year,
                round_number=meeting.get("round_number") or rounds.get(row["meeting_key"]),
                event_name=meeting.get("meeting_name") or row.get("location") or row.get("circuit_short_name") or "Race weekend",
                official_event_name=meeting.get("meeting_official_name"), country=openf1_host_country(circuit_key) or row.get("country_name"),
                circuit_key=str(circuit_key) if circuit_key is not None else None,
                location=row.get("location") or row.get("circuit_short_name"), is_testing=testing,
                session_name=row["session_name"], session_type=row.get("session_type"), scheduled_start_utc=start,
                available_for_import=available, unavailable_reason=reason))
        return sorted(output, key=lambda item: (item.scheduled_start_utc, item.source_session_key))
