"""Exercise actual Alembic history in an empty, disposable PostgreSQL schema."""

import os
from pathlib import Path
import subprocess
import sys
import unittest
from uuid import uuid4
from sqlalchemy import create_engine, text, select, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema
from app.config import settings
from modules.normalization.application.service import NormalizationService
from modules.session_domain.infrastructure.repository import SessionRepository
from modules.session_domain.infrastructure.db_models import SessionWeatherSampleRecord
from support import source_bundle


class MigrationTests(unittest.TestCase):
    def test_fresh_install_upgrade_downgrade_unit_repair_and_model_alignment(self):
        schema = "pw_migration_" + uuid4().hex
        admin = create_engine(settings.database_url)
        scoped = create_engine(
            settings.database_url, connect_args={"options": "-csearch_path=" + schema}
        )
        factory = sessionmaker(bind=scoped)
        environment = {
            **os.environ,
            "DATABASE_URL": settings.database_url,
            "PGOPTIONS": "-csearch_path=" + schema,
        }

        def migrate(*arguments):
            result = subprocess.run(
                [sys.executable, "-m", "alembic", *arguments],
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(
                result.returncode,
                0,
                (result.stdout + result.stderr).replace(
                    settings.database_url, "[test database]"
                ),
            )

        def wind():
            with factory() as db:
                return db.scalar(select(SessionWeatherSampleRecord.wind_speed_kph))

        try:
            with admin.begin() as connection:
                connection.execute(CreateSchema(schema))
            with scoped.connect() as connection:
                self.assertEqual(
                    connection.scalar(text("select current_schema()")), schema
                )
            migrate("upgrade", "c9f604e1d723")
            bundle = source_bundle()
            bundle.weather = [dict(SessionTime=0, WindSpeed=10)]
            snapshot = NormalizationService().build_snapshot(bundle, ttl_hours=1)
            with factory() as db:
                SessionRepository(db).import_snapshot(
                    snapshot, source_version="fixture", force_refresh=False
                )
                # Reproduce the legacy importer that stored m/s in a km/h column.
                db.execute(update(SessionWeatherSampleRecord).values(wind_speed_kph=10))
                db.commit()
            migrate("upgrade", "head")
            self.assertEqual(wind(), 36)
            migrate("check")
            migrate("upgrade", "head")
            self.assertEqual(wind(), 36)
            migrate("downgrade", "c9f604e1d723")
            self.assertEqual(wind(), 10)
            migrate("upgrade", "head")
            self.assertEqual(wind(), 36)
            migrate("check")
        finally:
            scoped.dispose()
            with admin.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True, if_exists=True))
            admin.dispose()
