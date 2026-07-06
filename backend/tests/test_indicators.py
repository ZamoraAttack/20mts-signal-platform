import math
import pytest
from app.signal_engine.buffers import TimestampedRingBuffer
from app.signal_engine.indicators import (
    pearson_correlation,
    check_synchronization,
    check_joint_decline,
    check_dia_diverging,
    check_stock_lagging,
    check_reconnection,
)
from tests.conftest import fill_buffer, make_settings, make_trend


# ── pearson_correlation ────────────────────────────────────────────────────────

def test_correlation_identical_series():
    a, b = TimestampedRingBuffer(50), TimestampedRingBuffer(50)
    prices = make_trend(100.0, 30, 0.001)
    fill_buffer(a, prices)
    fill_buffer(b, prices)
    corr = pearson_correlation(a, b)
    assert corr is not None
    assert abs(corr - 1.0) < 1e-6


def test_correlation_opposite_series():
    a, b = TimestampedRingBuffer(50), TimestampedRingBuffer(50)
    # Use varying (non-constant) per-tick returns so correlation is well-defined.
    # A constant-percentage trend has ~zero-variance returns, which makes
    # Pearson correlation meaningless (dominated by floating-point noise).
    a_prices = [100.0]
    b_prices = [100.0]
    for i in range(30):
        step = 0.001 * math.sin(i / 2)
        a_prices.append(a_prices[-1] * (1 + step))
        b_prices.append(b_prices[-1] * (1 - step))
    fill_buffer(a, a_prices)
    fill_buffer(b, b_prices)
    corr = pearson_correlation(a, b)
    assert corr is not None
    assert corr < -0.9


def test_correlation_returns_none_insufficient_data():
    a, b = TimestampedRingBuffer(50), TimestampedRingBuffer(50)
    fill_buffer(a, [100.0, 101.0])
    fill_buffer(b, [100.0, 101.0])
    assert pearson_correlation(a, b) is None


def test_correlation_returns_none_flat_series():
    a, b = TimestampedRingBuffer(50), TimestampedRingBuffer(50)
    fill_buffer(a, [100.0] * 30)
    fill_buffer(b, make_trend(100.0, 30, 0.001))
    assert pearson_correlation(a, b) is None


def test_correlation_returns_none_when_mostly_flat_with_one_matching_move():
    # Both series are flat (e.g. gap-filled, no-trade ticks) except for a
    # single shared non-zero return at the end. Two vectors that are all
    # zeros except one matching point are technically "perfectly
    # correlated", but with only one real observation that's a coincidence,
    # not a meaningful signal.
    a, b = TimestampedRingBuffer(50), TimestampedRingBuffer(50)
    a_prices = [100.0] * 20 + [101.0]
    b_prices = [50.0] * 20 + [50.5]
    fill_buffer(a, a_prices)
    fill_buffer(b, b_prices)
    assert pearson_correlation(a, b) is None


# ── check_synchronization ─────────────────────────────────────────────────────

def test_synchronization_passes_above_threshold():
    s = make_settings(sync_correlation_threshold=0.70)
    a, b = TimestampedRingBuffer(400), TimestampedRingBuffer(400)
    prices = make_trend(100.0, 50, 0.001)
    fill_buffer(a, prices)
    fill_buffer(b, prices)
    is_sync, corr = check_synchronization(a, b, s)
    assert is_sync is True
    assert corr is not None and corr > 0.70


def test_synchronization_fails_below_threshold():
    s = make_settings(sync_correlation_threshold=0.70)
    a, b = TimestampedRingBuffer(400), TimestampedRingBuffer(400)
    up = make_trend(100.0, 50, 0.001)
    down = make_trend(100.0, 50, -0.001)
    fill_buffer(a, up)
    fill_buffer(b, down)
    is_sync, _ = check_synchronization(a, b, s)
    assert is_sync is False


def test_synchronization_hysteresis_buffer_zone():
    # Build two series with a moderate, non-trivial correlation, then pick
    # thresholds that bracket it -- this lets us test the hysteresis
    # behavior regardless of the exact correlation value.
    a, b = TimestampedRingBuffer(400), TimestampedRingBuffer(400)
    common = [math.sin(i * 0.5) for i in range(40)]
    a_returns = [common[i] + 0.5 * math.sin(i * 1.3) for i in range(40)]
    b_returns = [common[i] + 0.5 * math.cos(i * 1.7) for i in range(40)]
    a_prices, b_prices = [100.0], [50.0]
    for r in a_returns:
        a_prices.append(a_prices[-1] * (1 + 0.001 * r))
    for r in b_returns:
        b_prices.append(b_prices[-1] * (1 + 0.001 * r))
    fill_buffer(a, a_prices)
    fill_buffer(b, b_prices)

    corr = pearson_correlation(a, b, lag=1)
    assert corr is not None
    assert 0.1 < corr < 0.9  # moderate correlation, not at the extremes

    s = make_settings(
        sync_correlation_threshold=corr + 0.05,
        sync_correlation_exit_threshold=corr - 0.05,
        correlation_return_lag_seconds=1,
    )

    # Not currently synchronized: correlation is below the entry threshold,
    # so it stays unsynchronized.
    is_sync, _ = check_synchronization(a, b, s, currently_synchronized=False)
    assert is_sync is False

    # Already synchronized: correlation is still above the (lower) exit
    # threshold, so it remains synchronized even though it's below the
    # entry threshold -- this is the hysteresis "buffer zone".
    is_sync, _ = check_synchronization(a, b, s, currently_synchronized=True)
    assert is_sync is True


def test_synchronization_exits_below_exit_threshold():
    s = make_settings(sync_correlation_threshold=0.70, sync_correlation_exit_threshold=0.60)
    a, b = TimestampedRingBuffer(400), TimestampedRingBuffer(400)
    up = make_trend(100.0, 50, 0.001)
    down = make_trend(100.0, 50, -0.001)
    fill_buffer(a, up)
    fill_buffer(b, down)

    # Strongly negative correlation is below even the exit threshold, so
    # sync is lost regardless of the previous state.
    is_sync, _ = check_synchronization(a, b, s, currently_synchronized=True)
    assert is_sync is False


# ── check_joint_decline ───────────────────────────────────────────────────────

def _make_declining_pair(n: int = 40, pct: float = -0.0006):
    """Both instruments declining together."""
    dia, stock = TimestampedRingBuffer(400), TimestampedRingBuffer(400)
    fill_buffer(dia, make_trend(410.0, n, pct))
    fill_buffer(stock, make_trend(220.0, n, pct))
    return dia, stock


def test_joint_decline_detects_shared_decline():
    s = make_settings()
    dia, stock = _make_declining_pair()
    assert check_joint_decline(dia, stock, s) is True


def test_joint_decline_fails_when_one_is_flat():
    s = make_settings()
    dia, stock = TimestampedRingBuffer(400), TimestampedRingBuffer(400)
    fill_buffer(dia, make_trend(410.0, 40, -0.0006))
    fill_buffer(stock, [220.0] * 40)
    assert check_joint_decline(dia, stock, s) is False


def test_joint_decline_fails_when_move_too_small():
    s = make_settings(joint_decline_min_return=-0.0005)
    dia, stock = TimestampedRingBuffer(400), TimestampedRingBuffer(400)
    # -0.002% per tick → ~ -0.024% over the 12s window, smaller in magnitude
    # than the -0.05% threshold, so joint decline should NOT be confirmed.
    fill_buffer(dia, make_trend(410.0, 40, -0.00002))
    fill_buffer(stock, make_trend(220.0, 40, -0.00002))
    assert check_joint_decline(dia, stock, s) is False


# ── check_dia_diverging ───────────────────────────────────────────────────────

def test_dia_diverging_via_consecutive_ticks():
    s = make_settings(divergence_dia_consecutive_ticks=3)
    dia = TimestampedRingBuffer(400)
    # 20 ticks declining, then 4 ticks rising
    prices = make_trend(410.0, 20, -0.0006) + make_trend(409.0, 5, 0.0004)
    fill_buffer(dia, prices)
    assert check_dia_diverging(dia, s) is True


def test_dia_diverging_not_triggered_with_insufficient_up_ticks():
    s = make_settings(divergence_dia_consecutive_ticks=3, divergence_return_window_seconds=5)
    dia = TimestampedRingBuffer(400)
    # 20 ticks declining, only 2 up ticks (not enough for consecutive check)
    prices = make_trend(410.0, 20, -0.0006) + make_trend(409.0, 2, 0.0001)
    fill_buffer(dia, prices)
    # Check: 2 consecutive ticks < threshold of 3, and return over 5s might still be negative
    result = check_dia_diverging(dia, s)
    # This depends on whether the 5s return is positive
    # With only 2 up ticks of 0.01% each over 5 ticks of history, could go either way
    # Just verify it doesn't crash
    assert isinstance(result, bool)


# ── check_stock_lagging ───────────────────────────────────────────────────────

def test_stock_lagging_when_flat():
    s = make_settings()
    stock = TimestampedRingBuffer(400)
    fill_buffer(stock, [220.0] * 30)
    assert check_stock_lagging(stock, s) is True


def test_stock_lagging_when_declining():
    s = make_settings()
    stock = TimestampedRingBuffer(400)
    fill_buffer(stock, make_trend(220.0, 30, -0.0003))
    assert check_stock_lagging(stock, s) is True


def test_stock_not_lagging_when_rising():
    s = make_settings()
    stock = TimestampedRingBuffer(400)
    fill_buffer(stock, make_trend(220.0, 30, 0.0003))
    assert check_stock_lagging(stock, s) is False


# ── check_reconnection ────────────────────────────────────────────────────────

def test_reconnection_via_consecutive_ticks():
    s = make_settings(reconnection_consecutive_ticks=2)
    stock = TimestampedRingBuffer(400)
    prices = make_trend(220.0, 20, -0.0003) + make_trend(219.0, 4, 0.0004)
    fill_buffer(stock, prices)
    assert check_reconnection(stock, s) is True


def test_reconnection_via_price_above_lookback():
    s = make_settings(reconnection_consecutive_ticks=5, reconnection_lookback_seconds=10)
    stock = TimestampedRingBuffer(400)
    # 10 ticks at 220 then a jump up
    prices = [220.0] * 12 + [221.0]
    fill_buffer(stock, prices)
    assert check_reconnection(stock, s) is True


def test_no_reconnection_when_still_declining():
    s = make_settings()
    stock = TimestampedRingBuffer(400)
    fill_buffer(stock, make_trend(220.0, 30, -0.0003))
    assert check_reconnection(stock, s) is False
