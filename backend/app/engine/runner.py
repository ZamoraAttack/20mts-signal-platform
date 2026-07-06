import logging
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import delete, select

from ..api.websockets.live import manager as ws_manager
from ..config import Settings
from ..data_feed import FeedManager, Tick
from ..database import AsyncSessionLocal
from ..models import JournalEntry, PriceTick, Signal, SignalOutcome, TradingSession
from .symbol_validation import InvalidSymbolError, validate_promotable_symbol
from ..signal_engine import (
    CorrelationWatchlist,
    OutcomeTracker,
    SignalEvent,
    SignalLogger,
    SignalState,
    SignalStateMachine,
    TrackedOutcome,
)

logger = logging.getLogger(__name__)

# Batches PriceTick inserts instead of one INSERT+commit per tick -- that
# per-tick round trip was the dominant bottleneck during bulk replay
# backtesting (~120 ticks/sec, ~10min for a 70k-tick day). Not a strategy
# parameter, so it isn't exposed via CONFIG_FIELD_MAP.
TICK_FLUSH_INTERVAL = 200


class EngineRunner:
    """
    Wires the data feed to the signal engine:

        FeedManager -> SignalStateMachine -> SignalLogger (PostgreSQL)
                                           -> WebSocket broadcast (live dashboard)

    Owns the trading session for "today" and persists every tick and signal event.
    """

    def __init__(self, feed_manager: FeedManager, settings: Settings):
        self.feed_manager = feed_manager
        self.settings = settings
        self.state_machine = SignalStateMachine(settings)
        self.watchlist = CorrelationWatchlist(settings)
        self.outcome_tracker = OutcomeTracker()
        self.session_id: str | None = None
        self._tick_buffer: list[dict] = []

    async def startup(self) -> None:
        async with AsyncSessionLocal() as db:
            self.session_id = await self._get_or_create_session(db)
        self.feed_manager.register(self.on_tick)
        logger.info("EngineRunner started — session_id=%s", self.session_id)

    async def set_active_stock(self, new_symbol: str) -> None:
        """
        Switches which stock the full state machine trades against. The new
        pairing starts fresh (no carried-over decline/divergence state from
        the old stock), and the feed is re-subscribed so ticks for the new
        symbol actually arrive.

        Validates the requested symbol first (non-empty, well-formed, and
        present in the configured watchlist) -- the engine must never
        silently switch to an invalid trading symbol. Raises
        InvalidSymbolError (caught by the route and turned into a 422) on
        any rejection; settings/state are left untouched in that case.
        """
        try:
            validated_symbol = validate_promotable_symbol(new_symbol, self.settings.watchlist_symbol_list)
        except InvalidSymbolError as exc:
            logger.warning(
                "Active stock promotion rejected: requested=%r current=%s reason=%s",
                new_symbol, self.settings.stock_symbol, exc,
            )
            raise

        old_symbol = self.settings.stock_symbol
        self.settings.stock_symbol = validated_symbol
        self.state_machine = SignalStateMachine(self.settings)
        await self.feed_manager.resubscribe()
        logger.info("Active stock switched %s -> %s", old_symbol, validated_symbol)

    async def _get_or_create_session(self, db) -> str:
        # ReplayFeed sets `session_date` (derived from the first tick's
        # timestamp) so historical replays land on their own day in the
        # Sessions list instead of "today". Live/simulated feeds leave this
        # unset and use today's date as before.
        replay_date: Optional[date] = getattr(self.feed_manager.feed, "session_date", None)
        session_date = replay_date or datetime.now(timezone.utc).date()

        result = await db.execute(
            select(TradingSession).where(TradingSession.session_date == session_date)
        )
        session = result.scalar_one_or_none()

        if session is not None:
            if replay_date is not None:
                # Re-running a replay for a date already analyzed — clear
                # prior ticks/signals so this run starts from a clean slate.
                await self._clear_session_data(db, session.id)
            return session.id

        session = TradingSession(
            session_date=session_date,
            stock_symbol=self.settings.stock_symbol,
            dia_symbol=self.settings.leader_symbol,
            created_at=datetime.now(timezone.utc),
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session.id

    async def _clear_session_data(self, db, session_id: str) -> None:
        await db.execute(
            delete(SignalOutcome).where(
                SignalOutcome.signal_id.in_(
                    select(Signal.id).where(Signal.session_id == session_id)
                )
            )
        )
        await db.execute(delete(JournalEntry).where(JournalEntry.session_id == session_id))
        await db.execute(delete(Signal).where(Signal.session_id == session_id))
        await db.execute(delete(PriceTick).where(PriceTick.session_id == session_id))
        await db.commit()
        logger.info("Cleared previous replay data for session %s", session_id)

    async def on_tick(self, tick: Tick, news_filter_active: bool, is_high_volatility: bool) -> None:
        self.watchlist.on_tick(tick.symbol, tick.price, tick.timestamp)

        # Only the leader and the currently-active stock drive the full
        # decline/divergence/reconnection state machine. Once FeedManager
        # subscribes to more symbols than just these two (for the passive
        # watchlist), every other symbol's ticks must be filtered out here
        # -- state_machine.on_tick() routes anything that isn't
        # leader_symbol straight into its single stock_buffer, so an
        # unfiltered watchlist tick would corrupt the active pairing.
        event: Optional[SignalEvent] = None
        if tick.symbol == self.settings.leader_symbol or tick.symbol == self.settings.stock_symbol:
            event = self.state_machine.on_tick(
                tick.symbol, tick.price, tick.timestamp, news_filter_active, is_high_volatility
            )

        if event and event.state == SignalState.SIGNAL_FIRED:
            self.outcome_tracker.start_tracking(
                event.signal_id, self.settings.stock_symbol, event.stock_price, event.timestamp
            )
        finalized_outcomes = self.outcome_tracker.on_tick(tick.symbol, tick.price, tick.timestamp)

        self._tick_buffer.append({
            "session_id": self.session_id,
            "symbol": tick.symbol,
            "price": tick.price,
            "tick_time": tick.timestamp,
            "is_high_vol": is_high_volatility,
        })
        if len(self._tick_buffer) >= TICK_FLUSH_INTERVAL:
            await self.flush_pending_ticks()

        if event or finalized_outcomes:
            async with AsyncSessionLocal() as db:
                if event:
                    signal_logger = SignalLogger(db, self.session_id, self.settings.stock_symbol)
                    await signal_logger.record(event)

                for tracked in finalized_outcomes:
                    await self._persist_outcome(db, tracked)
                    self.outcome_tracker.pop_finalized(tracked.signal_id)

        await ws_manager.broadcast({
            "type": "tick",
            "symbol": tick.symbol,
            "price": tick.price,
            "timestamp": tick.timestamp.isoformat(),
            "status": self.status_dict(),
        })

        if event:
            await ws_manager.broadcast({
                "type": "signal_event",
                "event": self._event_dict(event),
            })

    async def flush_pending_ticks(self) -> None:
        """Bulk-inserts whatever PriceTicks have accumulated since the last
        flush. Called every TICK_FLUSH_INTERVAL ticks, and once more by the
        feed-completion handler in main.py so the final partial batch (and
        any live/simulated-feed shutdown) isn't lost."""
        if not self._tick_buffer:
            return
        batch, self._tick_buffer = self._tick_buffer, []
        async with AsyncSessionLocal() as db:
            await db.execute(PriceTick.__table__.insert(), batch)
            await db.commit()

    async def _persist_outcome(self, db, tracked: TrackedOutcome) -> None:
        """
        Auto-populates SignalOutcome's price-tracking fields once a tracked
        signal's window has elapsed. Only ever sets price-derived fields --
        never was_successful/was_red_herring/u_shape_type/notes, which stay
        human-editable via PUT /api/signals/{id}/outcome.
        """
        max_gain_pct = (tracked.peak_price - tracked.price_at_signal) / tracked.price_at_signal * 100
        max_drawdown_pct = (tracked.trough_price - tracked.price_at_signal) / tracked.price_at_signal * 100
        gain_at_window_pct = (
            (tracked.price_at_window_end - tracked.price_at_signal) / tracked.price_at_signal * 100
            if tracked.price_at_window_end is not None
            else None
        )

        result = await db.execute(select(SignalOutcome).where(SignalOutcome.signal_id == tracked.signal_id))
        outcome = result.scalar_one_or_none()
        if outcome is None:
            outcome = SignalOutcome(signal_id=tracked.signal_id, recorded_at=datetime.now(timezone.utc))
            db.add(outcome)

        outcome.price_at_signal = tracked.price_at_signal
        outcome.price_peak_20min = tracked.peak_price
        outcome.price_at_20min = tracked.price_at_window_end
        outcome.max_gain_pct = max_gain_pct
        outcome.gain_at_20min_pct = gain_at_window_pct
        outcome.seconds_to_peak = tracked.peak_seconds_to_peak
        outcome.price_trough_20min = tracked.trough_price
        outcome.seconds_to_trough = tracked.trough_seconds_to_trough
        outcome.max_drawdown_pct = max_drawdown_pct
        outcome.recorded_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info(
            "Outcome auto-tracked  signal=%s  max_gain=%.2f%%  max_drawdown=%.2f%%  gain_at_window=%s",
            tracked.signal_id, max_gain_pct, max_drawdown_pct, gain_at_window_pct,
        )

    def status_dict(self) -> dict:
        s = self.state_machine.status()
        return {
            "state": s.state.value,
            "correlation": s.correlation,
            "is_synchronized": s.is_synchronized,
            "dia_price": s.dia_price,
            "stock_price": s.stock_price,
            "leader_symbol": self.settings.leader_symbol,
            "stock_symbol": self.settings.stock_symbol,
            "tick_count": s.tick_count,
            "active_signal_id": s.active_signal_id,
            "divergence_start_time": s.divergence_start_time.isoformat() if s.divergence_start_time else None,
            "news_filter_active": self.settings.news_filter_active,
            "data_feed_provider": self.settings.data_feed_provider,
        }

    def _event_dict(self, event: SignalEvent) -> dict:
        return {
            "signal_id": event.signal_id,
            "state": event.state.value,
            "timestamp": event.timestamp.isoformat(),
            "dia_price": event.dia_price,
            "stock_price": event.stock_price,
            "correlation": event.correlation,
            "divergence_seconds_elapsed": event.divergence_seconds_elapsed,
            "notes": event.notes,
        }
