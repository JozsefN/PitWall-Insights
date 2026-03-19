from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from modules.storage.infrastructure.base import Base


class SessionRecord(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    track_code: Mapped[str] = mapped_column(String(64), nullable=False)
    driver_code: Mapped[str] = mapped_column(String(64), nullable=False)
    lap_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)