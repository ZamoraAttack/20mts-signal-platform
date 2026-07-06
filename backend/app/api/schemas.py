from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ── Signals ────────────────────────────────────────────────────────────────

class SignalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: Optional[str]
    stock_symbol: str

    divergence_dia_price: Optional[float]
    divergence_stock_price: Optional[float]
    signal_dia_price: Optional[float]
    signal_stock_price: Optional[float]

    divergence_detected_at: datetime
    signal_fired_at: Optional[datetime]
    expired_at: Optional[datetime]
    divergence_seconds: Optional[float]

    correlation_at_signal: Optional[float]
    outcome: Optional[str]

    is_high_volatility: bool
    news_filter_active: bool
    u_shape_detected: bool

    notes: Optional[str]
    created_at: datetime


class SignalOutcomeUpsert(BaseModel):
    # Optional (not required) so a partial update -- e.g. a human editing
    # only was_successful/notes on a row the auto-tracker already
    # populated -- doesn't have to resend it. Still required when creating
    # a brand-new row; enforced in the route, since the DB column is
    # NOT NULL.
    price_at_signal: Optional[float] = None
    price_peak_20min: Optional[float] = None
    price_at_20min: Optional[float] = None
    max_gain_pct: Optional[float] = None
    gain_at_20min_pct: Optional[float] = None
    seconds_to_peak: Optional[float] = None
    price_trough_20min: Optional[float] = None
    seconds_to_trough: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    was_successful: Optional[bool] = None
    was_red_herring: bool = False
    u_shape_type: Optional[str] = None
    notes: Optional[str] = None


class SignalOutcomeRead(SignalOutcomeUpsert):
    model_config = ConfigDict(from_attributes=True)

    id: str
    signal_id: str
    recorded_at: datetime


class TickPoint(BaseModel):
    symbol: str
    tick_time: datetime
    price: float


class SignalSuggestionRead(BaseModel):
    profitable_at_20min: Optional[bool]
    hit_target: Optional[bool]
    suggested_was_red_herring: Optional[bool]
    suggested_u_shape_type: Optional[str]
    classification: Optional[str]
    notes: str


class SignalDetailRead(BaseModel):
    signal: SignalRead
    outcome: Optional[SignalOutcomeRead]
    leader_symbol: str
    ticks: list[TickPoint]
    suggestion: SignalSuggestionRead


# ── Journal ───────────────────────────────────────────────────────────────

class JournalEntryCreate(BaseModel):
    session_id: Optional[str] = None
    signal_id: Optional[str] = None
    entry_type: str
    body: str


class JournalEntryRead(JournalEntryCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entry_time: datetime


# ── Config ────────────────────────────────────────────────────────────────

class ConfigItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: str
    description: Optional[str] = None


class ConfigUpdate(BaseModel):
    value: str


# ── Sessions ──────────────────────────────────────────────────────────────

class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_date: date
    stock_symbol: str
    dia_symbol: str
    notes: Optional[str] = None
    created_at: datetime


class SessionStats(BaseModel):
    session_id: str
    session_date: date
    total_signals: int
    fired: int
    expired: int
    win_rate: Optional[float]
    avg_divergence_seconds: Optional[float]


class DivergenceBucketStats(BaseModel):
    bucket: str
    total_signals: int
    wins: int
    decided: int
    win_rate: Optional[float]
    avg_max_gain_pct: Optional[float]
    avg_gain_at_20min_pct: Optional[float]


class StockAnalytics(BaseModel):
    stock_symbol: str
    total_signals: int
    wins: int
    decided: int
    win_rate: Optional[float]
    avg_max_gain_pct: Optional[float]
    avg_gain_at_20min_pct: Optional[float]


class DayAnalytics(BaseModel):
    session_date: date
    total_signals: int
    wins: int
    decided: int
    win_rate: Optional[float]
    avg_max_gain_pct: Optional[float]
    avg_gain_at_20min_pct: Optional[float]


class TimeOfDayAnalytics(BaseModel):
    hour_bucket: str
    total_signals: int
    wins: int
    decided: int
    win_rate: Optional[float]
    avg_max_gain_pct: Optional[float]
    avg_gain_at_20min_pct: Optional[float]


# ── Engine status ─────────────────────────────────────────────────────────

class EngineStatusRead(BaseModel):
    state: str
    correlation: Optional[float]
    is_synchronized: bool
    dia_price: Optional[float]
    stock_price: Optional[float]
    leader_symbol: str
    stock_symbol: str
    tick_count: int
    active_signal_id: Optional[str]
    divergence_start_time: Optional[datetime]
    news_filter_active: bool
    data_feed_provider: str


class NewsFilterUpdate(BaseModel):
    active: bool


class ActiveStockUpdate(BaseModel):
    symbol: str


class WatchlistRead(BaseModel):
    leader_symbol: str
    active_symbol: str
    candidates: dict[str, Optional[float]]
