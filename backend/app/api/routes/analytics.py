from zoneinfo import ZoneInfo

from fastapi import APIRouter
from sqlalchemy import func, select

from ...database import AsyncSessionLocal
from ...models import Signal, SignalOutcome, TradingSession
from ..schemas import DayAnalytics, StockAnalytics, TimeOfDayAnalytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

ET = ZoneInfo("America/New_York")


def _stats_from_rows(rows, schema_cls, label_field: str):
    """
    Shared row->schema mapper for the grouped (label, total, wins, decided,
    avg_max_gain, avg_gain_20) shape every analytics endpoint here produces
    -- same win-rate/avg-gain convention as
    routes/sessions.py's _bucket_stats_from_rows, just parameterized over
    which field holds the group label (stock_symbol / session_date /
    hour_bucket) since that's the only thing that differs between them.
    """
    return [
        schema_cls(**{
            label_field: label,
            "total_signals": total,
            "wins": wins,
            "decided": decided,
            "win_rate": (wins / decided) if decided else None,
            "avg_max_gain_pct": float(avg_max_gain) if avg_max_gain is not None else None,
            "avg_gain_at_20min_pct": float(avg_gain_20) if avg_gain_20 is not None else None,
        })
        for label, total, wins, decided, avg_max_gain, avg_gain_20 in rows
    ]


@router.get("/by-stock", response_model=list[StockAnalytics])
async def get_analytics_by_stock():
    """Average gain + signal frequency grouped by stock_symbol -- "compared
    to what" baseline across every stock that's ever been the active pairing."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(
                Signal.stock_symbol,
                func.count(Signal.id),
                func.count(SignalOutcome.id).filter(SignalOutcome.was_successful.is_(True)),
                func.count(SignalOutcome.id).filter(SignalOutcome.was_successful.is_not(None)),
                func.avg(SignalOutcome.max_gain_pct),
                func.avg(SignalOutcome.gain_at_20min_pct),
            )
            .select_from(Signal)
            .outerjoin(SignalOutcome, SignalOutcome.signal_id == Signal.id)
            .group_by(Signal.stock_symbol)
        )
        return _stats_from_rows(result.all(), StockAnalytics, "stock_symbol")


@router.get("/by-day", response_model=list[DayAnalytics])
async def get_analytics_by_day():
    """Average gain + signal frequency grouped by calendar day (session_date)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(
                TradingSession.session_date,
                func.count(Signal.id),
                func.count(SignalOutcome.id).filter(SignalOutcome.was_successful.is_(True)),
                func.count(SignalOutcome.id).filter(SignalOutcome.was_successful.is_not(None)),
                func.avg(SignalOutcome.max_gain_pct),
                func.avg(SignalOutcome.gain_at_20min_pct),
            )
            .select_from(Signal)
            .join(TradingSession, TradingSession.id == Signal.session_id)
            .outerjoin(SignalOutcome, SignalOutcome.signal_id == Signal.id)
            .group_by(TradingSession.session_date)
            .order_by(TradingSession.session_date)
        )
        return _stats_from_rows(result.all(), DayAnalytics, "session_date")


@router.get("/by-time-of-day", response_model=list[TimeOfDayAnalytics])
async def get_analytics_by_time_of_day():
    """
    Average gain + signal frequency grouped by ET hour-of-day. Aggregated
    in Python rather than SQL: signal volume is small at this stage of the
    project, and timezone-bucketing in Postgres would need a date_trunc
    with an explicit AT TIME ZONE conversion for no real benefit yet.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(
                Signal.divergence_detected_at,
                SignalOutcome.was_successful,
                SignalOutcome.max_gain_pct,
                SignalOutcome.gain_at_20min_pct,
            )
            .select_from(Signal)
            .outerjoin(SignalOutcome, SignalOutcome.signal_id == Signal.id)
        )
        rows = result.all()

    buckets: dict[int, dict] = {}
    for detected_at, was_successful, max_gain_pct, gain_at_20min_pct in rows:
        hour = detected_at.astimezone(ET).hour
        b = buckets.setdefault(hour, {"total": 0, "wins": 0, "decided": 0, "gains": [], "gains_20": []})
        b["total"] += 1
        if was_successful is True:
            b["wins"] += 1
        if was_successful is not None:
            b["decided"] += 1
        if max_gain_pct is not None:
            b["gains"].append(float(max_gain_pct))
        if gain_at_20min_pct is not None:
            b["gains_20"].append(float(gain_at_20min_pct))

    return [
        TimeOfDayAnalytics(
            hour_bucket=f"{hour}:00-{hour + 1}:00",
            total_signals=b["total"],
            wins=b["wins"],
            decided=b["decided"],
            win_rate=(b["wins"] / b["decided"]) if b["decided"] else None,
            avg_max_gain_pct=(sum(b["gains"]) / len(b["gains"])) if b["gains"] else None,
            avg_gain_at_20min_pct=(sum(b["gains_20"]) / len(b["gains_20"])) if b["gains_20"] else None,
        )
        for hour, b in sorted(buckets.items())
    ]
