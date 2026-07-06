import uuid
from datetime import date, datetime
from sqlalchemy import Date, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class TradingSession(Base):
    __tablename__ = "trading_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    stock_symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    dia_symbol: Mapped[str] = mapped_column(String(10), nullable=False, default="DIA")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
