import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("trading_sessions.id"))
    stock_symbol: Mapped[str] = mapped_column(String(10), nullable=False)

    # Prices at key moments
    divergence_dia_price: Mapped[float | None] = mapped_column(Numeric(12, 4))
    divergence_stock_price: Mapped[float | None] = mapped_column(Numeric(12, 4))
    signal_dia_price: Mapped[float | None] = mapped_column(Numeric(12, 4))
    signal_stock_price: Mapped[float | None] = mapped_column(Numeric(12, 4))

    # Timing
    divergence_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    signal_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    divergence_seconds: Mapped[float | None] = mapped_column(Numeric(6, 2))

    # Metrics
    correlation_at_signal: Mapped[float | None] = mapped_column(Numeric(6, 4))

    # Outcome: 'pending' | 'fired' | 'expired' | 'filtered'
    outcome: Mapped[str | None] = mapped_column(String(20))

    # Regime flags
    is_high_volatility: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    news_filter_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    u_shape_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SignalOutcome(Base):
    __tablename__ = "signal_outcomes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    signal_id: Mapped[str] = mapped_column(String(36), ForeignKey("signals.id"), unique=True)

    price_at_signal: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    price_peak_20min: Mapped[float | None] = mapped_column(Numeric(12, 4))
    price_at_20min: Mapped[float | None] = mapped_column(Numeric(12, 4))
    max_gain_pct: Mapped[float | None] = mapped_column(Numeric(8, 4))
    gain_at_20min_pct: Mapped[float | None] = mapped_column(Numeric(8, 4))
    seconds_to_peak: Mapped[float | None] = mapped_column(Numeric(8, 2))

    # Drawdown: the symmetric "worst dip below entry" counterpart to peak,
    # tracked the same way by OutcomeTracker.
    price_trough_20min: Mapped[float | None] = mapped_column(Numeric(12, 4))
    seconds_to_trough: Mapped[float | None] = mapped_column(Numeric(8, 2))
    max_drawdown_pct: Mapped[float | None] = mapped_column(Numeric(8, 4))

    was_successful: Mapped[bool | None] = mapped_column(Boolean)
    was_red_herring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # 'sub_1min' | '1min' | '2min' | '3min' | 'none'
    u_shape_type: Mapped[str | None] = mapped_column(String(20))

    notes: Mapped[str | None] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("trading_sessions.id"))
    signal_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("signals.id"))
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # 'observation' | 'note' | 'rule' | 'question'
    entry_type: Mapped[str] = mapped_column(String(20), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
