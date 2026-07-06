from typing import Optional
import numpy as np

from .buffers import TimestampedRingBuffer
from ..config import Settings


def pearson_correlation(buf_a: TimestampedRingBuffer, buf_b: TimestampedRingBuffer, lag: int = 1) -> Optional[float]:
    """Pearson correlation of n-tick returns between two instruments."""
    ret_a = buf_a.returns_n_tick(lag)
    ret_b = buf_b.returns_n_tick(lag)

    n = min(len(ret_a), len(ret_b))
    if n < 10:
        return None

    a = np.array(ret_a[-n:])
    b = np.array(ret_b[-n:])

    if np.std(a) == 0 or np.std(b) == 0:
        return None

    # Require enough actual price movement in both series. With heavy
    # gap-filling (no-trade ticks repeat the last price -> 0 return), a
    # window dominated by zeros can show spurious correlation of exactly
    # +/-1 if by coincidence only one or two non-zero returns line up.
    if np.count_nonzero(a) < 10 or np.count_nonzero(b) < 10:
        return None

    return float(np.corrcoef(a, b)[0, 1])


def check_synchronization(
    dia_buf: TimestampedRingBuffer,
    stock_buf: TimestampedRingBuffer,
    settings: Settings,
    currently_synchronized: bool = False,
) -> tuple[bool, Optional[float]]:
    """
    Returns (is_synchronized, correlation).
    Synchronization = Pearson correlation of N-second returns over the sync window.

    Uses hysteresis to avoid flickering when correlation hovers near the
    threshold: entering "synchronized" requires correlation >=
    sync_correlation_threshold, but once synchronized it only exits if
    correlation drops below the lower sync_correlation_exit_threshold.
    """
    corr = pearson_correlation(dia_buf, stock_buf, lag=settings.correlation_return_lag_seconds)
    if corr is None:
        return False, None

    if currently_synchronized:
        return corr >= settings.sync_correlation_exit_threshold, corr
    return corr >= settings.sync_correlation_threshold, corr


def check_joint_decline(
    dia_buf: TimestampedRingBuffer,
    stock_buf: TimestampedRingBuffer,
    settings: Settings,
) -> bool:
    """
    Both instruments must:
      - have returned < joint_decline_min_return over the window, AND
      - be trading below their short-term EMA
    """
    window = settings.joint_decline_window_seconds
    threshold = settings.joint_decline_min_return
    ema_period = settings.ema_period_seconds

    dia_ret = dia_buf.recent_return(window)
    stock_ret = stock_buf.recent_return(window)

    if dia_ret is None or stock_ret is None:
        return False
    if dia_ret >= threshold or stock_ret >= threshold:
        return False

    dia_price = dia_buf.current_price()
    stock_price = stock_buf.current_price()
    dia_ema = dia_buf.current_ema(ema_period)
    stock_ema = stock_buf.current_ema(ema_period)

    if None in (dia_price, stock_price, dia_ema, stock_ema):
        return False

    return dia_price < dia_ema and stock_price < stock_ema  # type: ignore[operator]


def check_dia_diverging(dia_buf: TimestampedRingBuffer, settings: Settings) -> bool:
    """
    DIA has shifted from negative/flat to positive — confirmed by EITHER:
      - 3+ consecutive upward ticks, OR
      - positive return over the last 5 ticks
    """
    if dia_buf.consecutive_up_ticks() >= settings.divergence_dia_consecutive_ticks:
        return True

    ret = dia_buf.recent_return(settings.divergence_return_window_seconds)
    return ret is not None and ret > 0


def check_stock_lagging(stock_buf: TimestampedRingBuffer, settings: Settings) -> bool:
    """Stock has NOT yet turned positive (still flat or declining)."""
    ret = stock_buf.recent_return(settings.divergence_return_window_seconds)
    if ret is None:
        return True
    return ret <= 0


def check_reconnection(stock_buf: TimestampedRingBuffer, settings: Settings) -> bool:
    """
    Stock begins following DIA upward — confirmed by EITHER:
      - 2+ consecutive upward ticks, OR
      - current price above price reconnection_lookback_seconds ticks ago
    """
    if stock_buf.consecutive_up_ticks() >= settings.reconnection_consecutive_ticks:
        return True

    past_price = stock_buf.price_n_ticks_ago(settings.reconnection_lookback_seconds)
    current = stock_buf.current_price()
    if past_price is not None and current is not None:
        return current > past_price

    return False
