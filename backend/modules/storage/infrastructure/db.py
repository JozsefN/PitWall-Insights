from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


engine = create_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


# Keep all SQLAlchemy tables registered on shared metadata before repository
# code starts mutating records with cross-module foreign keys.
from modules.dashboard_layouts.infrastructure import db_models as _dashboard_layouts_db_models  # noqa: E402,F401
from modules.identity_auth.infrastructure import db_models as _identity_auth_db_models  # noqa: E402,F401
from modules.session_domain.infrastructure import db_models as _session_domain_db_models  # noqa: E402,F401
from modules.session_import.infrastructure import db_models as _session_import_db_models  # noqa: E402,F401
from modules.telemetry_materialization.infrastructure import db_models as _telemetry_materialization_db_models  # noqa: E402,F401


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Database:
    def health(self) -> dict:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return {
                "status": "connected",
                "driver": "postgresql",
            }
        except Exception as exc:
            return {
                "status": "disconnected",
                "driver": "postgresql",
                "error": str(exc),
            }
