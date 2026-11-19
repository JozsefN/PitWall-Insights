"""Real free-source import -> queued materialization -> reads/strategy in a disposable schema."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import perf_counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from support import isolated_database
from sqlalchemy import func
from modules.ingestion.infrastructure.provider_registry import build_session_source
from modules.normalization.application.service import NormalizationService
from modules.session_domain.domain.models import SessionImportRequest
from modules.session_domain.infrastructure.repository import SessionRepository
from modules.session_domain.infrastructure.models import SessionEntryRecord, EntryLapRecord, CarTelemetrySampleRecord, PositionSampleRecord
from modules.telemetry_materialization.application.service import TelemetryMaterializationService
from modules.telemetry_materialization.domain.models import TelemetryMaterializationRequest
from modules.identity_auth.infrastructure.db_models import UserRecord
from modules.feature_metrics.domain.strategy.models import StrategyRequest
from modules.decision_engine.application.strategy_service import StrategyService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year",type=int,default=2025)
    parser.add_argument("--round",type=int,default=1)
    parser.add_argument("--drivers",default="1,4,16")
    parser.add_argument("--output",default="../docs/testing/hybrid-openf1-validation.json")
    args = parser.parse_args()
    begin = perf_counter()
    bundle = build_session_source("openf1").load_session(SessionImportRequest(season_year=args.year,round_number=args.round,session_name="Race"))
    source_seconds = perf_counter()-begin
    report = {"checked_at_utc":datetime.now(timezone.utc).isoformat(),"session":bundle.catalog_item.source_session_key,
              "provider":"openf1","account_or_subscription_used":False,"core_source_seconds":round(source_seconds,3),
              "quality_policy":bundle.metadata.session_info["quality_policy"],"clean_laps":bundle.metadata.session_info["clean_lap_count"],
              "coverage":bundle.metadata.session_info["coverage"]}
    with isolated_database() as factory:
        with factory() as db:
            db.add(UserRecord(id="verification-user",email="verification@example.com",password_hash="test-fixture"))
            db.commit()
            snapshot = NormalizationService().build_snapshot(bundle,ttl_hours=1)
            sid = SessionRepository(db).import_snapshot(snapshot,source_version=bundle.source_version,force_refresh=False)
            entries = db.query(SessionEntryRecord).filter(SessionEntryRecord.session_id==sid,SessionEntryRecord.car_number.in_(args.drivers.split(","))).order_by(SessionEntryRecord.car_number).all()
            if not entries:
                raise RuntimeError("No selected drivers")
            ids = [entry.id for entry in entries]
            report["selected_drivers"] = [entry.car_number for entry in entries]
            queued = TelemetryMaterializationService(db).ensure_materialization(TelemetryMaterializationRequest(session_id=sid,entry_ids=ids,kinds=["car","position"],scope="session"))
            job = TelemetryMaterializationService(db).run_next_job()
            if job is None or job.status != "completed":
                raise RuntimeError(job.error_message if job else "Worker did not claim the job")
            report.update(job_status=job.status,telemetry_rows=job.rows_written,startup_seconds=round(perf_counter()-begin,3))
            ready = TelemetryMaterializationService(db).ensure_materialization(TelemetryMaterializationRequest(session_id=sid,entry_ids=ids,kinds=["car","position"],scope="session"))
            assert ready.ready
            report["repeat_ensure_ready"] = ready.ready
            cutoff = db.query(func.max(EntryLapRecord.lap_end_time_ms)).join(SessionEntryRecord).filter(SessionEntryRecord.session_id==sid).scalar()
            result = StrategyService(db).evaluate(sid,"verification-user",StrategyRequest(focus_entry_id=ids[0],rival_entry_ids=ids[1:],as_of_ms=cutoff,mode="counterfactual"))
            report["strategy_metric_values"] = len(result.values)
            report["strategy_available_values"] = sum(v.status!="unavailable" for v in result.values)
            report["strategy_status"] = result.recommendation_status
            report["timeline"] = SessionRepository(db).get_replay_timeline(sid)
            report["supplement_rows"] = {name:len(bundle.metadata.session_info.get(name,[])) for name in ("pit_stops","intervals","race_positions","lap_quality","starting_grid","overtakes")}
    report["disposable_schema_removed"] = True
    Path(args.output).write_text(json.dumps(report,indent=2,default=str)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2,default=str))


if __name__ == "__main__":
    main()
