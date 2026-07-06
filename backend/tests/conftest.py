from datetime import datetime, timezone, timedelta
import pytest
from app.config import Settings
from app.signal_engine.buffers import TimestampedRingBuffer


def make_settings(**overrides) -> Settings:
    defaults = dict(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        sync_window_seconds=300,
        sync_correlation_threshold=0.70,
        joint_decline_window_seconds=12,
        joint_decline_min_return=-0.0005,
        ema_period_seconds=25,
        divergence_dia_consecutive_ticks=3,
        divergence_return_window_seconds=5,
        divergence_expiry_seconds=120,
        reconnection_consecutive_ticks=2,
        reconnection_lookback_seconds=10,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def fill_buffer(buf: TimestampedRingBuffer, prices: list[float], base_time: datetime | None = None) -> None:
    """Push a list of prices into a buffer with 1-second spacing."""
    t = base_time or datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc)
    for i, p in enumerate(prices):
        buf.push(p, t + timedelta(seconds=i))


def make_trend(start: float, num: int, pct_per_tick: float) -> list[float]:
    """Generate a price series with a constant percentage move per tick."""
    prices = [start]
    for _ in range(num - 1):
        prices.append(prices[-1] * (1 + pct_per_tick))
    return prices
