from datetime import datetime, timedelta, timezone

from app.signal_engine.watchlist import CorrelationWatchlist
from tests.conftest import make_settings, make_trend


def _push(watchlist: CorrelationWatchlist, symbol: str, prices: list[float]) -> None:
    base = datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc)
    for i, p in enumerate(prices):
        watchlist.on_tick(symbol, p, base + timedelta(seconds=i))


def test_snapshot_reports_correlation_for_synced_candidate():
    s = make_settings(leader_symbol="DIA", watchlist_symbols="NFLX")
    wl = CorrelationWatchlist(s)
    prices = make_trend(100.0, 30, 0.001)
    _push(wl, "DIA", prices)
    _push(wl, "NFLX", prices)

    snap = wl.snapshot()
    assert snap["NFLX"] is not None
    assert snap["NFLX"] > 0.9


def test_snapshot_returns_none_for_candidate_with_no_ticks():
    s = make_settings(leader_symbol="DIA", watchlist_symbols="NFLX,AAPL")
    wl = CorrelationWatchlist(s)
    _push(wl, "DIA", make_trend(100.0, 30, 0.001))
    _push(wl, "NFLX", make_trend(100.0, 30, 0.001))
    # AAPL never ticks

    snap = wl.snapshot()
    assert snap["NFLX"] is not None
    assert snap["AAPL"] is None


def test_snapshot_returns_none_for_all_candidates_before_leader_ticks():
    s = make_settings(leader_symbol="DIA", watchlist_symbols="NFLX")
    wl = CorrelationWatchlist(s)
    _push(wl, "NFLX", make_trend(100.0, 30, 0.001))
    # DIA (leader) never ticks

    snap = wl.snapshot()
    assert snap == {"NFLX": None}


def test_on_tick_ignores_untracked_symbols():
    s = make_settings(leader_symbol="DIA", watchlist_symbols="NFLX")
    wl = CorrelationWatchlist(s)
    wl.on_tick("META", 100.0, datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc))
    assert "META" not in wl._buffers
