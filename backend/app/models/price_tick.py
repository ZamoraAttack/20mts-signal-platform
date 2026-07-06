from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PriceTick(Base):
    __tablename__ = "price_ticks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("trading_sessions.id"))
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    tick_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_high_vol: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
