from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TrackedOutcome:
    signal_id: str
    stock_symbol: str
    price_at_signal: float
    window_start: datetime
    window_seconds: int
    peak_price: float
    peak_seconds_to_peak: float
    trough_price: float
    trough_seconds_to_trough: float
    price_at_window_end: Optional[float] = None


class OutcomeTracker:
    """
    Watches ticks after a SIGNAL_FIRED event to auto-populate SignalOutcome's
    price-tracking fields (peak price, price at the window mark, gain %,
    seconds to peak) -- replacing today's fully-manual entry. Subjective
    fields (was_successful, was_red_herring, u_shape_type, notes) are never
    touched here; those stay human-editable via the existing PUT endpoint.

    Pure in-memory bookkeeping, no DB access -- the caller (EngineRunner)
    persists finalized entries.

    window_seconds defaults to 1200 (20 minutes), matching the fixed
    measurement convention already baked into the SignalOutcome column
    names (price_peak_20min, gain_at_20min_pct) -- this is not a tunable
    strategy parameter, so it isn't exposed via CONFIG_FIELD_MAP.
    """

    def __init__(self, window_seconds: int = 1200):
        self.window_seconds = window_seconds
        self._active: dict[str, TrackedOutcome] = {}

    def start_tracking(
        self, signal_id: str, stock_symbol: str, price_at_signal: float, fired_at: datetime
    ) -> None:
        self._active[signal_id] = TrackedOutcome(
            signal_id=signal_id,
            stock_symbol=stock_symbol,
            price_at_signal=price_at_signal,
            window_start=fired_at,
            window_seconds=self.window_seconds,
            peak_price=price_at_signal,
            peak_seconds_to_peak=0.0,
            trough_price=price_at_signal,
            trough_seconds_to_trough=0.0,
        )

    def on_tick(self, symbol: str, price: float, timestamp: datetime) -> list[TrackedOutcome]:
        """Updates peak/time-to-peak for matching in-flight trackers; returns
        the ones that just crossed window_seconds elapsed (ready to persist
        and remove via pop_finalized)."""
        finalized: list[TrackedOutcome] = []
        for tracked in self._active.values():
            if tracked.stock_symbol != symbol:
                continue

            elapsed = (timestamp - tracked.window_start).total_seconds()
            if elapsed < 0:
                continue

            if price > tracked.peak_price:
                tracked.peak_price = price
                tracked.peak_seconds_to_peak = elapsed

            if price < tracked.trough_price:
                tracked.trough_price = price
                tracked.trough_seconds_to_trough = elapsed

            if elapsed >= tracked.window_seconds and tracked.price_at_window_end is None:
                tracked.price_at_window_end = price
                finalized.append(tracked)

        return finalized

    def pop_finalized(self, signal_id: str) -> Optional[TrackedOutcome]:
        return self._active.pop(signal_id, None)
