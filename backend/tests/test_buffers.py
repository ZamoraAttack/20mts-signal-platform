from datetime import datetime, timezone, timedelta
import pytest
from app.signal_engine.buffers import TimestampedRingBuffer
from tests.conftest import fill_buffer, make_trend


def test_capacity_enforced():
    buf = TimestampedRingBuffer(10)
    fill_buffer(buf, list(range(1, 20)))
    assert len(buf) == 10


def test_current_price_returns_latest():
    buf = TimestampedRingBuffer(50)
    fill_buffer(buf, [100.0, 101.0, 102.5])
    assert buf.current_price() == 102.5


def test_returns_1tick_length():
    buf = TimestampedRingBuffer(50)
    fill_buffer(buf, [100.0, 101.0, 102.0])
    rets = buf.returns_1tick()
    assert len(rets) == 2


def test_returns_1tick_values():
    buf = TimestampedRingBuffer(50)
    fill_buffer(buf, [100.0, 110.0])
    rets = buf.returns_1tick()
    assert abs(rets[0] - 0.10) < 1e-9


def test_recent_return_positive():
    buf = TimestampedRingBuffer(50)
    prices = make_trend(100.0, 15, 0.001)
    fill_buffer(buf, prices)
    ret = buf.recent_return(10)
    assert ret is not None and ret > 0


def test_recent_return_negative():
    buf = TimestampedRingBuffer(50)
    prices = make_trend(100.0, 15, -0.001)
    fill_buffer(buf, prices)
    ret = buf.recent_return(10)
    assert ret is not None and ret < 0


def test_recent_return_none_when_insufficient_data():
    buf = TimestampedRingBuffer(50)
    fill_buffer(buf, [100.0, 101.0])
    assert buf.recent_return(10) is None


def test_price_n_ticks_ago():
    buf = TimestampedRingBuffer(50)
    fill_buffer(buf, [10.0, 20.0, 30.0, 40.0, 50.0])
    assert buf.price_n_ticks_ago(2) == 30.0


def test_consecutive_up_ticks_count():
    buf = TimestampedRingBuffer(50)
    # flat, then 4 up ticks
    fill_buffer(buf, [100.0, 100.0, 101.0, 102.0, 103.0, 104.0])
    assert buf.consecutive_up_ticks() == 4


def test_consecutive_up_ticks_reset_on_down():
    buf = TimestampedRingBuffer(50)
    fill_buffer(buf, [100.0, 101.0, 102.0, 101.5])
    assert buf.consecutive_up_ticks() == 0


def test_ema_flat_price():
    buf = TimestampedRingBuffer(50)
    fill_buffer(buf, [100.0] * 30)
    ema = buf.current_ema(25)
    assert ema is not None
    assert abs(ema - 100.0) < 1e-6


def test_ema_rising_price_below_current():
    buf = TimestampedRingBuffer(50)
    prices = make_trend(100.0, 30, 0.002)
    fill_buffer(buf, prices)
    ema = buf.current_ema(25)
    current = buf.current_price()
    assert ema is not None and current is not None
    assert current > ema
