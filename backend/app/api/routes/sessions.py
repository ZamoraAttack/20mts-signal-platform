import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from ...database import AsyncSessionLocal
from ...models import PriceTick, Signal, SignalOutcome, TradingSession
from ...signal_engine.bucketing import bucket_case_expr
from ..schemas import DivergenceBucketStats, SessionRead, SessionStats

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionRead])
async def list_sessions():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TradingSession).order_by(TradingSession.session_date.desc())
        )
        return result.scalars().all()


@router.get("/today", response_model=SessionRead)
async def get_today_session():
    today = datetime.now(timezone.utc).date()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TradingSession).where(TradingSession.session_date == today)
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(status_code=404, detail="No session recorded for today")
        return session


@router.get("/{session_id}/export")
async def export_session_ticks(session_id: str):
    """
    Export this session's price ticks as a CSV in the format ReplayFeed reads
    (timestamp,symbol,price,volume,bid,ask), so any session — live, simulated,
    or a prior replay — can be saved and re-streamed later for backtesting.
    """
    async with AsyncSessionLocal() as db:
        session = await db.get(TradingSession, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        result = await db.execute(
            select(PriceTick)
            .where(PriceTick.session_id == session_id)
            .order_by(PriceTick.tick_time, PriceTick.symbol)
        )
        ticks = result.scalars().all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["timestamp", "symbol", "price", "volume", "bid", "ask"])
    for tick in ticks:
        writer.writerow([tick.tick_time.isoformat(), tick.symbol, tick.price, "", "", ""])
    buffer.seek(0)

    filename = f"replay_{session.session_date}.csv"
    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{session_id}/stats", response_model=SessionStats)
async def get_session_stats(session_id: str):
    async with AsyncSessionLocal() as db:
        session = await db.get(TradingSession, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        counts_result = await db.execute(
            select(
                func.count(Signal.id),
                func.count(Signal.id).filter(Signal.outcome == "fired"),
                func.count(Signal.id).filter(Signal.outcome == "expired"),
                func.avg(Signal.divergence_seconds),
            ).where(Signal.session_id == session_id)
        )
        total_signals, fired, expired, avg_divergence_seconds = counts_result.one()

        win_result = await db.execute(
            select(
                func.count(SignalOutcome.id).filter(SignalOutcome.was_successful.is_(True)),
                func.count(SignalOutcome.id).filter(SignalOutcome.was_successful.is_not(None)),
            )
            .join(Signal, Signal.id == SignalOutcome.signal_id)
            .where(Signal.session_id == session_id)
        )
        wins, decided = win_result.one()
        win_rate = (wins / decided) if decided else None

        return SessionStats(
            session_id=session_id,
            session_date=session.session_date,
            total_signals=total_signals or 0,
            fired=fired or 0,
            expired=expired or 0,
            win_rate=win_rate,
            avg_divergence_seconds=float(avg_divergence_seconds) if avg_divergence_seconds is not None else None,
        )


@router.get("/{session_id}/stats/by-divergence-bucket", response_model=list[DivergenceBucketStats])
async def get_session_stats_by_bucket(session_id: str):
    """
    Read-only research view: groups this session's signals by how long the
    divergence lasted before firing/expiring, joined to outcome data where
    recorded. Never used to filter/suppress signals — purely so the data can
    later reveal whether short divergences actually under-perform.
    """
    async with AsyncSessionLocal() as db:
        session = await db.get(TradingSession, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        bucket = bucket_case_expr(Signal.divergence_seconds)
        result = await db.execute(
            select(
                bucket,
                func.count(Signal.id),
                func.count(SignalOutcome.id).filter(SignalOutcome.was_successful.is_(True)),
                func.count(SignalOutcome.id).filter(SignalOutcome.was_successful.is_not(None)),
                func.avg(SignalOutcome.max_gain_pct),
                func.avg(SignalOutcome.gain_at_20min_pct),
            )
            .select_from(Signal)
            .outerjoin(SignalOutcome, SignalOutcome.signal_id == Signal.id)
            .where(Signal.session_id == session_id, Signal.divergence_seconds.is_not(None))
            .group_by(bucket)
        )
        return _bucket_stats_from_rows(result.all())


def _bucket_stats_from_rows(rows) -> list[DivergenceBucketStats]:
    return [
        DivergenceBucketStats(
            bucket=bucket,
            total_signals=total,
            wins=wins,
            decided=decided,
            win_rate=(wins / decided) if decided else None,
            avg_max_gain_pct=float(avg_max_gain) if avg_max_gain is not None else None,
            avg_gain_at_20min_pct=float(avg_gain_20) if avg_gain_20 is not None else None,
        )
        for bucket, total, wins, decided, avg_max_gain, avg_gain_20 in rows
    ]
