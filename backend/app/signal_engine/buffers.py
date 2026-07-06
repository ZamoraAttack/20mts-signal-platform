from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class PriceTick:
    price: float
    timestamp: datetime


class TimestampedRingBuffer:
    """
    Fixed-capacity circular buffer of (price, timestamp) pairs.
    Capacity is in ticks, not seconds — designed for 1-second data where 1 tick ≈ 1 second.
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._data: deque[PriceTick] = deque(maxlen=capacity)

    def push(self, price: float, timestamp: datetime) -> None:
        self._data.append(PriceTick(price=price, timestamp=timestamp))

    def __len__(self) -> int:
        return len(self._data)

    def is_empty(self) -> bool:
        return len(self._data) == 0

    def current_price(self) -> Optional[float]:
        return self._data[-1].price if self._data else None

    def prices(self) -> list[float]:
        return [t.price for t in self._data]

    def price_n_ticks_ago(self, n: int) -> Optional[float]:
        """Price n ticks back from current. n=1 means one tick ago."""
        if len(self._data) <= n:
            return None
        return self._data[-(n + 1)].price

    def returns_1tick(self) -> list[float]:
        """1-tick percentage returns for the full buffer."""
        return self.returns_n_tick(1)

    def returns_n_tick(self, n: int) -> list[float]:
        """
        Overlapping n-tick percentage returns for the full buffer: each value
        is the percentage change from n ticks ago to the current tick.
        """
        prices = self.prices()
        if len(prices) <= n:
            return []
        return [(prices[i] - prices[i - n]) / prices[i - n] for i in range(n, len(prices))]

    def recent_return(self, window_ticks: int) -> Optional[float]:
        """Percentage return from window_ticks ago to now."""
        past = self.price_n_ticks_ago(window_ticks)
        current = self.current_price()
        if past is None or current is None or past == 0:
            return None
        return (current - past) / past

    def current_ema(self, period: int) -> Optional[float]:
        """Exponential moving average over the full buffer using given period."""
        prices = self.prices()
        if not prices:
            return None
        alpha = 2.0 / (period + 1)
        ema = prices[0]
        for p in prices[1:]:
            ema = p * alpha + ema * (1 - alpha)
        return ema

    def last_n_tick_directions(self, n: int) -> list[int]:
        """
        Returns a list of n direction values for the most recent n ticks.
        1 = price went up, -1 = price went down, 0 = unchanged.
        """
        prices = self.prices()
        if len(prices) < 2:
            return []
        tail = prices[-(n + 1):]
        return [
            1 if tail[i] > tail[i - 1] else (-1 if tail[i] < tail[i - 1] else 0)
            for i in range(1, len(tail))
        ]

    def consecutive_up_ticks(self, max_look: int = 20) -> int:
        """Count the current trailing run of consecutive upward ticks."""
        directions = self.last_n_tick_directions(max_look)
        count = 0
        for d in reversed(directions):
            if d == 1:
                count += 1
            else:
                break
        return count
