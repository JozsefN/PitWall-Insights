"""Build inspectable historical cohorts from already materialized data; no source download."""

import argparse
from datetime import timedelta
from pathlib import Path
import sys
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.storage.infrastructure.db import SessionLocal
from modules.session_domain.infrastructure.db_models import (
    SessionEntryRecord,
    CarTelemetrySampleRecord,
)
from modules.feature_metrics.infrastructure.analysis_input import AnalysisInputProvider
from modules.feature_metrics.domain.analysis.models import AnalysisRequest
from modules.feature_metrics.domain.strategy.history import collect_incident_history
from modules.feature_metrics.domain.strategy.models import StrategyContext

parser = argparse.ArgumentParser()
parser.add_argument("session_ids", nargs="+")
parser.add_argument("--circuit-key", required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
history = []
for identity in args.session_ids:
    with SessionLocal() as db:
        provider = AnalysisInputProvider(db)
        data = provider.load(
            identity,
            AnalysisRequest(sample_interval_ms=1000),
            required_inputs={"car", "laps", "track_status"},
        )
        dated = db.execute(
            select(
                CarTelemetrySampleRecord.source_time_utc,
                CarTelemetrySampleRecord.session_time_ms,
            )
            .join(
                SessionEntryRecord,
                SessionEntryRecord.id == CarTelemetrySampleRecord.session_entry_id,
            )
            .where(
                SessionEntryRecord.session_id == identity,
                CarTelemetrySampleRecord.source_time_utc.is_not(None),
            )
            .order_by(
                CarTelemetrySampleRecord.session_entry_id,
                CarTelemetrySampleRecord.session_time_ms,
            )
            .limit(1)
        ).first()
        if dated is None:
            raise ValueError("Session lacks dated materialized car observations")
        history.extend(
            collect_incident_history(
                data,
                circuit_key=args.circuit_key,
                clock_origin=dated[0] - timedelta(milliseconds=dated[1]),
            )
        )
context = StrategyContext(
    known_at_ms=0,
    source_note="Retrospective censored stationary-car cohorts. Unknown spatial/recovery geometry; not independently validated. Inspect and merge with context before use.",
    incident_history=history,
)
args.output.write_text(context.model_dump_json(indent=2) + "\n", encoding="utf-8")
print(
    f"Exported {len(history)} labelled observations; no DB/source mutation. Cohorts still require held-out review."
)
