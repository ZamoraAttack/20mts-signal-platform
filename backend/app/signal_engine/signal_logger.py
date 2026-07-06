import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.signal import Signal
from .state_machine import SignalEvent, SignalState

logger = logging.getLogger(__name__)


class SignalLogger:
    """
    Persists every signal event to PostgreSQL.
    Tracks pending divergence records and updates them when signals fire or expire.
    """

    def __init__(self, db: AsyncSession, session_id: str, stock_symbol: str):
        self.db = db
        self.session_id = session_id
        self.stock_symbol = stock_symbol
        self._pending: dict[str, Signal] = {}

    async def record(self, event: SignalEvent) -> None:
        if event.state == SignalState.DIVERGENCE:
            await self._on_divergence(event)
        elif event.state == SignalState.SIGNAL_FIRED:
            await self._on_fired(event)
        elif event.state == SignalState.SIGNAL_EXPIRED:
            await self._on_expired(event)

    async def _on_divergence(self, event: SignalEvent) -> None:
        now = datetime.now(timezone.utc)
        signal = Signal(
            id=event.signal_id,
            session_id=self.session_id,
            stock_symbol=self.stock_symbol,
            divergence_dia_price=event.dia_price,
            divergence_stock_price=event.stock_price,
            divergence_detected_at=event.timestamp,
            correlation_at_signal=event.correlation,
            outcome="pending",
            is_high_volatility=event.is_high_volatility,
            news_filter_active=False,
            created_at=now,
        )
        self.db.add(signal)
        await self.db.commit()
        await self.db.refresh(signal)
        self._pending[event.signal_id] = signal
        logger.info("Signal created  id=%s", event.signal_id)

    async def _on_fired(self, event: SignalEvent) -> None:
        signal = await self._get_or_load(event.signal_id)
        if signal is None:
            return
        signal.signal_fired_at = event.timestamp
        signal.signal_dia_price = event.dia_price
        signal.signal_stock_price = event.stock_price
        signal.divergence_seconds = event.divergence_seconds_elapsed
        signal.outcome = "fired"
        signal.notes = event.notes
        await self.db.commit()
        self._pending.pop(event.signal_id, None)
        logger.info("Signal fired  id=%s  elapsed=%.1fs", event.signal_id, event.divergence_seconds_elapsed)

    async def _on_expired(self, event: SignalEvent) -> None:
        signal = await self._get_or_load(event.signal_id)
        if signal is None:
            return
        signal.expired_at = event.timestamp
        signal.divergence_seconds = event.divergence_seconds_elapsed
        signal.outcome = "expired"
        signal.notes = event.notes
        await self.db.commit()
        self._pending.pop(event.signal_id, None)
        logger.info("Signal expired  id=%s  elapsed=%.1fs", event.signal_id, event.divergence_seconds_elapsed)

    async def _get_or_load(self, signal_id: str) -> Optional[Signal]:
        if signal_id in self._pending:
            return self._pending[signal_id]
        result = await self.db.get(Signal, signal_id)
        if result is None:
            logger.warning("Signal %s not found in database", signal_id)
        return result
