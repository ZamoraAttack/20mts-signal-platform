from datetime import datetime
from typing import Optional

from .buffers import TimestampedRingBuffer
from .indicators import pearson_correlation
from ..config import Settings


class CorrelationWatchlist:
    """
    Passive, read-only correlation screener — replaces "watching several
    TradingView panes to see which stock is synced today."

    Deliberately separate from SignalStateMachine: no states, no decline/
    divergence/reconnection logic, no thresholds-as-filters. It only answers
    "how correlated is this candidate with the leader right now," for the
    leader plus every configured watchlist symbol (the currently-active
    stock_symbol is included automatically if it's also in the watchlist).
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        buffer_capacity = settings.sync_window_seconds + 120
        self._buffer_capacity = buffer_capacity
        self._buffers: dict[str, TimestampedRingBuffer] = {}

    def _buffer_for(self, symbol: str) -> TimestampedRingBuffer:
        if symbol not in self._buffers:
            self._buffers[symbol] = TimestampedRingBuffer(self._buffer_capacity)
        return self._buffers[symbol]

    def on_tick(self, symbol: str, price: float, timestamp: datetime) -> None:
        tracked = {self.settings.leader_symbol, *self.settings.watchlist_symbol_list}
        if symbol not in tracked:
            return
        self._buffer_for(symbol).push(price, timestamp)

    def snapshot(self) -> dict[str, Optional[float]]:
        leader_symbol = self.settings.leader_symbol
        if leader_symbol not in self._buffers:
            return {symbol: None for symbol in self.settings.watchlist_symbol_list}

        leader_buf = self._buffers[leader_symbol]
        result: dict[str, Optional[float]] = {}
        for symbol in self.settings.watchlist_symbol_list:
            candidate_buf = self._buffers.get(symbol)
            if candidate_buf is None:
                result[symbol] = None
                continue
            result[symbol] = pearson_correlation(
                leader_buf, candidate_buf, lag=self.settings.correlation_return_lag_seconds
            )
        return result
