"""
Historical replay data feed for backtesting/validation.

Reads a long-format CSV of historical 1-second ticks (one row per symbol per
timestamp) and streams them through the same `Tick` interface as
SimulatedFeed/SchwabFeed, so the existing engine, API, and dashboard work
unchanged against historical data.

Expected CSV columns:
    timestamp   ISO-8601 datetime with timezone offset (e.g. 2025-03-17T09:30:00-04:00)
    symbol      Must match settings.leader_symbol or settings.stock_symbol
    price       Last/trade price (required)
    volume      Optional, integer
    bid         Optional, float
    ask         Optional, float

Rows for the leader and follower symbol are interleaved in the same file;
the loader sorts by timestamp regardless of input order.

The replayed session is dated from the first tick's timestamp (converted to
America/New_York), so each historical day shows up as its own row on the
Sessions page rather than mixing with "today". EngineRunner reads
`session_date` off this feed to do that.
"""

import asyncio
import csv
import logging
from collections.abc import AsyncIterator
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from .base import DataFeed, Tick

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")


class ReplayFeed(DataFeed):
    """Streams historical ticks from a CSV file."""

    def __init__(self, file_path: str, speed: float = 0.0):
        self.file_path = file_path
        self.speed = speed
        self._ticks: list[Tick] = []
        self._symbols: list[str] = []
        self.session_date: Optional[date] = None

    async def connect(self) -> None:
        self._ticks = self._load_csv()
        if self._ticks:
            self.session_date = self._ticks[0].timestamp.astimezone(ET).date()
        logger.info(
            "ReplayFeed loaded %d ticks from %s (session_date=%s, speed=%s)",
            len(self._ticks), self.file_path, self.session_date, self.speed,
        )

    def _load_csv(self) -> list[Tick]:
        ticks: list[Tick] = []
        with open(self.file_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ticks.append(Tick(
                    symbol=row["symbol"].strip(),
                    price=float(row["price"]),
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    volume=int(row["volume"]) if row.get("volume") else None,
                    bid=float(row["bid"]) if row.get("bid") else None,
                    ask=float(row["ask"]) if row.get("ask") else None,
                ))
        ticks.sort(key=lambda t: t.timestamp)
        return ticks

    async def subscribe(self, symbols: list[str]) -> None:
        self._symbols = symbols

    async def stream(self) -> AsyncIterator[Tick]:
        prev_ts: Optional[datetime] = None
        for tick in self._ticks:
            if tick.symbol not in self._symbols:
                continue
            if self.speed > 0 and prev_ts is not None:
                gap = (tick.timestamp - prev_ts).total_seconds()
                if gap > 0:
                    await asyncio.sleep(gap / self.speed)
            prev_ts = tick.timestamp
            yield tick
        logger.info("ReplayFeed finished streaming %s", self.file_path)

    async def disconnect(self) -> None:
        pass
