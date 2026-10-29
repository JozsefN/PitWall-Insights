from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, Index, BigInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from modules.storage.infrastructure.base import Base


class SessionAnalysisCacheRecord(Base):
    __tablename__ = "session_analysis_cache"
    __table_args__ = (
        Index("ix_session_analysis_cache_session_expires", "session_id", "expires_at"),
        Index("ix_analysis_cache_owner_session", "owner_user_id", "session_id"),
    )
    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_user_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "users.id", ondelete="CASCADE", name="fk_analysis_cache_owner_user_id"
        ),
        nullable=True,
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("event_sessions.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    data_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


class StrategyContextRecord(Base):
    __tablename__ = "strategy_context_versions"
    __table_args__ = (
        Index(
            "ix_strategy_context_owner_session",
            "owner_user_id",
            "session_id",
            "created_at",
        ),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("event_sessions.id", ondelete="CASCADE"), nullable=False
    )
    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    known_at_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
