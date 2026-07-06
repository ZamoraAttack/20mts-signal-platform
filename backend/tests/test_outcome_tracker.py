from datetime import datetime, timedelta, timezone

from app.signal_engine.outcome_tracker import OutcomeTracker

START = datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc)


def test_tracks_peak_price_and_time_to_peak():
    tracker = OutcomeTracker(window_seconds=20)
    tracker.start_tracking("sig-1", "NFLX", price_at_signal=100.0, fired_at=START)

    tracker.on_tick("NFLX", 101.0, START + timedelta(seconds=5))
    tracker.on_tick("NFLX", 103.0, START + timedelta(seconds=10))
    tracker.on_tick("NFLX", 102.0, START + timedelta(seconds=15))

    tracked = tracker._active["sig-1"]
    assert tracked.peak_price == 103.0
    assert tracked.peak_seconds_to_peak == 10.0


def test_finalizes_exactly_once_when_window_elapses():
    tracker = OutcomeTracker(window_seconds=20)
    tracker.start_tracking("sig-1", "NFLX", price_at_signal=100.0, fired_at=START)

    finalized = tracker.on_tick("NFLX", 105.0, START + timedelta(seconds=10))
    assert finalized == []

    finalized = tracker.on_tick("NFLX", 110.0, START + timedelta(seconds=20))
    assert len(finalized) == 1
    assert finalized[0].signal_id == "sig-1"
    assert finalized[0].price_at_window_end == 110.0

    # A later tick for the same (already-finalized-but-not-popped) signal
    # must not finalize it again.
    finalized = tracker.on_tick("NFLX", 111.0, START + timedelta(seconds=25))
    assert finalized == []


def test_ignores_ticks_for_other_symbols():
    tracker = OutcomeTracker(window_seconds=20)
    tracker.start_tracking("sig-1", "NFLX", price_at_signal=100.0, fired_at=START)

    finalized = tracker.on_tick("AAPL", 500.0, START + timedelta(seconds=25))
    assert finalized == []
    assert tracker._active["sig-1"].peak_price == 100.0


def test_pop_finalized_removes_entry():
    tracker = OutcomeTracker(window_seconds=20)
    tracker.start_tracking("sig-1", "NFLX", price_at_signal=100.0, fired_at=START)
    tracker.on_tick("NFLX", 100.0, START + timedelta(seconds=20))

    popped = tracker.pop_finalized("sig-1")
    assert popped is not None
    assert tracker.pop_finalized("sig-1") is None
    assert "sig-1" not in tracker._active


def test_tracks_trough_price_and_time_to_trough():
    tracker = OutcomeTracker(window_seconds=20)
    tracker.start_tracking("sig-1", "NFLX", price_at_signal=100.0, fired_at=START)

    tracker.on_tick("NFLX", 99.0, START + timedelta(seconds=5))
    tracker.on_tick("NFLX", 97.0, START + timedelta(seconds=10))
    tracker.on_tick("NFLX", 98.0, START + timedelta(seconds=15))

    tracked = tracker._active["sig-1"]
    assert tracked.trough_price == 97.0
    assert tracked.trough_seconds_to_trough == 10.0


def test_trough_does_not_update_on_higher_tick():
    tracker = OutcomeTracker(window_seconds=20)
    tracker.start_tracking("sig-1", "NFLX", price_at_signal=100.0, fired_at=START)

    tracker.on_tick("NFLX", 95.0, START + timedelta(seconds=5))
    tracker.on_tick("NFLX", 110.0, START + timedelta(seconds=10))

    tracked = tracker._active["sig-1"]
    assert tracked.trough_price == 95.0
    assert tracked.trough_seconds_to_trough == 5.0
    assert tracked.peak_price == 110.0


def test_trough_defaults_to_entry_price_when_price_only_rises():
    tracker = OutcomeTracker(window_seconds=20)
    tracker.start_tracking("sig-1", "NFLX", price_at_signal=100.0, fired_at=START)

    tracker.on_tick("NFLX", 101.0, START + timedelta(seconds=5))
    tracker.on_tick("NFLX", 105.0, START + timedelta(seconds=10))

    tracked = tracker._active["sig-1"]
    assert tracked.trough_price == 100.0
    assert tracked.trough_seconds_to_trough == 0.0


def test_supports_multiple_concurrent_signals():
    tracker = OutcomeTracker(window_seconds=20)
    tracker.start_tracking("sig-1", "NFLX", price_at_signal=100.0, fired_at=START)
    tracker.start_tracking("sig-2", "AAPL", price_at_signal=200.0, fired_at=START + timedelta(seconds=5))

    tracker.on_tick("NFLX", 105.0, START + timedelta(seconds=10))
    tracker.on_tick("AAPL", 205.0, START + timedelta(seconds=10))

    assert tracker._active["sig-1"].peak_price == 105.0
    assert tracker._active["sig-2"].peak_price == 205.0
