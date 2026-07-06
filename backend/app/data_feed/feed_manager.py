import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .base import DataFeed, Tick
from ..config import settings

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")

TickHandler = Callable[[Tick, bool, bool], Awaitable[None]]


def _market_regime(ts: datetime) -> tuple[bool, bool]:
    """
    Returns (is_market_open, is_high_volatility) for a given UTC timestamp.
    Market open: 9:30–16:00 ET.
    High volatility: first and last 30 minutes of the session.
    """
    local = ts.astimezone(ET)
    open_minutes = settings.market_open_hour * 60 + settings.market_open_minute
    close_minutes = settings.market_close_hour * 60 + settings.market_close_minute
    now_minutes = local.hour * 60 + local.minute

    if now_minutes < open_minutes or now_minutes >= close_minutes:
        return False, False

    hv_window = settings.high_volatility_window_minutes
    is_high_vol = (
        now_minutes < open_minutes + hv_window
        or now_minutes >= close_minutes - hv_window
    )
    return True, is_high_vol


class FeedManager:
    """
    Owns the data feed lifecycle and routes incoming ticks to registered handlers.

    Handlers receive: (tick, is_high_volatility) — market-hours filtering happens here
    so downstream components (signal engine) never need to think about it.
    """

    def __init__(self, feed: DataFeed):
        self.feed = feed
        self._handlers: list[TickHandler] = []
        self._running = False
        self._latest: dict[str, Tick] = {}

    def register(self, handler: TickHandler) -> None:
        self._handlers.append(handler)

    async def connect(self) -> None:
        await self.feed.connect()
        await self.feed.subscribe(self._symbols())
        logger.info("FeedManager connected — symbols: %s", self._symbols())

    def _symbols(self) -> list[str]:
        active = [settings.leader_symbol, settings.stock_symbol]
        watchlist = [s for s in settings.watchlist_symbol_list if s not in active]
        return active + watchlist

    async def resubscribe(self) -> None:
        """Re-issues subscribe() with the current symbol set — used after an
        active-stock switch or a watchlist edit so a running feed picks up
        the change without a full reconnect."""
        await self.feed.subscribe(self._symbols())
        logger.info("FeedManager re-subscribed — symbols: %s", self._symbols())

    async def start(self) -> None:
        self._running = True
        async for tick in self.feed.stream():
            if not self._running:
                break

            is_open, is_high_vol = _market_regime(tick.timestamp)
            if settings.respect_market_hours and not is_open:
                continue

            self._latest[tick.symbol] = tick
            await self._dispatch(tick, is_high_vol)

    async def _dispatch(self, tick: Tick, is_high_volatility: bool) -> None:
        for handler in self._handlers:
            try:
                await handler(tick, settings.news_filter_active, is_high_volatility)
            except Exception:
                logger.exception("Handler error on tick %s @ %.4f", tick.symbol, tick.price)

    async def stop(self) -> None:
        self._running = False
        await self.feed.disconnect()
        logger.info("FeedManager stopped")
