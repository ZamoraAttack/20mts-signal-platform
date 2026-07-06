import asyncio
import math
import random
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Optional

from .base import DataFeed, Tick


class SimulatedFeed(DataFeed):
    """
    Synthetic correlated price feed for development and testing.
    Generates DIA and one stock ticker with configurable correlation using a common-shock model.
    Both instruments emit one tick per interval (simulating 1-second bars).
    """

    def __init__(
        self,
        correlation: float = 0.85,
        tick_interval: float = 1.0,
        seed: Optional[int] = None,
        symbol_correlations: Optional[dict[str, float]] = None,
    ):
        self.correlation = correlation
        # Dev/test fixture only: per-symbol correlation override, so a
        # watchlist of several synthetic candidates can show distinguishable
        # sync levels instead of every non-leader symbol sharing one global
        # correlation value. Falls back to `correlation` for any symbol not
        # listed here.
        self.symbol_correlations = symbol_correlations or {}
        self.tick_interval = tick_interval
        self._prices: dict[str, float] = {}
        self._symbols: list[str] = []
        self._running = False
        if seed is not None:
            random.seed(seed)

    async def connect(self) -> None:
        self._running = True

    async def subscribe(self, symbols: list[str]) -> None:
        self._symbols = symbols
        for sym in symbols:
            # Only seed a starting price for symbols not already tracked --
            # subscribe() may be called again later (e.g. an active-stock
            # switch or watchlist edit), and re-seeding an existing symbol
            # would snap its price back to the start value mid-stream.
            if sym not in self._prices:
                self._prices[sym] = 410.00 if sym == "DIA" else 220.00

    async def stream(self) -> AsyncIterator[Tick]:
        while self._running:
            await asyncio.sleep(self.tick_interval)
            now = datetime.now(timezone.utc)

            common_shock = random.gauss(0, 0.0002)

            for sym in self._symbols:
                idio = random.gauss(0, 0.0001)
                if sym == "DIA":
                    ret = common_shock + idio
                else:
                    corr = self.symbol_correlations.get(sym, self.correlation)
                    ret = corr * common_shock + math.sqrt(max(0.0, 1 - corr ** 2)) * idio
                self._prices[sym] *= 1 + ret
                yield Tick(symbol=sym, price=round(self._prices[sym], 4), timestamp=now)

    async def disconnect(self) -> None:
        self._running = False
