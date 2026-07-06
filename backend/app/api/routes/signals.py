from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from ...database import AsyncSessionLocal
from ...models import PriceTick, Signal, SignalOutcome, TradingSession
from ...signal_engine.bucketing import bucket_case_expr
from ...signal_engine.suggestion import suggest_outcome
from ..schemas import (
    DivergenceBucketStats,
    SignalDetailRead,
    SignalOutcomeRead,
    SignalOutcomeUpsert,
    SignalRead,
    SignalSuggestionRead,
    TickPoint,
)
from .sessions import _bucket_stats_from_rows

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("", response_model=list[SignalRead])
async def list_signals(session_id: str | None = None, outcome: str | None = None):
    async with AsyncSessionLocal() as db:
        stmt = select(Signal).order_by(Signal.divergence_detected_at.desc())
        if session_id:
            stmt = stmt.where(Signal.session_id == session_id)
        if outcome:
            stmt = stmt.where(Signal.outcome == outcome)
        result = await db.execute(stmt)
        return result.scalars().all()


@router.get("/{signal_id}", response_model=SignalRead)
async def get_signal(signal_id: str):
    async with AsyncSessionLocal() as db:
        signal = await db.get(Signal, signal_id)
        if signal is None:
            raise HTTPException(status_code=404, detail="Signal not found")
        return signal


@router.get("/{signal_id}/outcome", response_model=SignalOutcomeRead)
async def get_signal_outcome(signal_id: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SignalOutcome).where(SignalOutcome.signal_id == signal_id)
        )
        outcome = result.scalar_one_or_none()
        if outcome is None:
            raise HTTPException(status_code=404, detail="Outcome not recorded for this signal")
        return outcome


@router.put("/{signal_id}/outcome", response_model=SignalOutcomeRead)
async def upsert_signal_outcome(signal_id: str, payload: SignalOutcomeUpsert):
    async with AsyncSessionLocal() as db:
        signal = await db.get(Signal, signal_id)
        if signal is None:
            raise HTTPException(status_code=404, detail="Signal not found")

        result = await db.execute(
            select(SignalOutcome).where(SignalOutcome.signal_id == signal_id)
        )
        outcome = result.scalar_one_or_none()

        if outcome is None:
            if payload.price_at_signal is None:
                raise HTTPException(
                    status_code=422, detail="price_at_signal is required when creating a new outcome"
                )
            outcome = SignalOutcome(
                signal_id=signal_id,
                recorded_at=datetime.now(timezone.utc),
                **payload.model_dump(),
            )
            db.add(outcome)
        else:
            # exclude_unset: only overwrite fields the caller actually sent,
            # so a human editing just was_successful/notes doesn't stomp
            # price fields the auto-tracker already populated, and vice versa.
            for field, value in payload.model_dump(exclude_unset=True).items():
                setattr(outcome, field, value)
            outcome.recorded_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(outcome)
        return outcome


@router.get("/{signal_id}/detail", response_model=SignalDetailRead)
async def get_signal_detail(signal_id: str, before_seconds: int = 300, after_seconds: int = 1200):
    """
    Everything a human needs to review one signal in one call: the signal,
    its outcome (if tracked), a replay window of raw price ticks around it
    (for charting), and an objective, non-binding suggestion derived from
    the outcome data. Default window is a 5-minute lookback from the signal
    point through the full 20-minute outcome-tracking window -- anchored on
    signal_fired_at (falling back to divergence_detected_at for expired
    signals, which never reached a fire point). 5 minutes comfortably
    covers the divergence point too, since divergence-to-fire is capped at
    divergence_expiry_seconds (120s by default).
    """
    async with AsyncSessionLocal() as db:
        signal = await db.get(Signal, signal_id)
        if signal is None:
            raise HTTPException(status_code=404, detail="Signal not found")

        outcome_result = await db.execute(
            select(SignalOutcome).where(SignalOutcome.signal_id == signal_id)
        )
        outcome = outcome_result.scalar_one_or_none()

        session = await db.get(TradingSession, signal.session_id) if signal.session_id else None
        leader_symbol = session.dia_symbol if session else "DIA"

        anchor = signal.signal_fired_at or signal.divergence_detected_at
        window_start = anchor - timedelta(seconds=before_seconds)
        window_end = anchor + timedelta(seconds=after_seconds)

        ticks_result = await db.execute(
            select(PriceTick)
            .where(
                PriceTick.session_id == signal.session_id,
                PriceTick.symbol.in_([leader_symbol, signal.stock_symbol]),
                PriceTick.tick_time.between(window_start, window_end),
            )
            .order_by(PriceTick.tick_time)
        )
        ticks = ticks_result.scalars().all()

        suggestion = suggest_outcome(outcome)

        return SignalDetailRead(
            signal=SignalRead.model_validate(signal),
            outcome=SignalOutcomeRead.model_validate(outcome) if outcome else None,
            leader_symbol=leader_symbol,
            ticks=[TickPoint(symbol=t.symbol, tick_time=t.tick_time, price=t.price) for t in ticks],
            suggestion=SignalSuggestionRead(
                profitable_at_20min=suggestion.profitable_at_20min,
                hit_target=suggestion.hit_target,
                suggested_was_red_herring=suggestion.suggested_was_red_herring,
                suggested_u_shape_type=suggestion.suggested_u_shape_type,
                classification=suggestion.classification,
                notes=suggestion.notes,
            ),
        )


@router.get("/stats/by-divergence-bucket", response_model=list[DivergenceBucketStats])
async def get_all_time_stats_by_bucket():
    """
    Same breakdown as GET /api/sessions/{id}/stats/by-divergence-bucket but
    across every session — "track which durations produce the best outcomes"
    reads as a cross-day research question, not a per-day one.
    """
    async with AsyncSessionLocal() as db:
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
            .where(Signal.divergence_seconds.is_not(None))
            .group_by(bucket)
        )
        return _bucket_stats_from_rows(result.all())
