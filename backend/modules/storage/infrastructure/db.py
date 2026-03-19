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


def get_db_session() -> Generator[Session, None, None]:
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