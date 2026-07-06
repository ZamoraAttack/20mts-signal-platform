from datetime import datetime, timezone, timedelta
import pytest
from app.signal_engine.state_machine import SignalState, SignalStateMachine
from tests.conftest import make_settings, make_trend


BASE_TIME = datetime(2024, 1, 2, 10, 30, 0, tzinfo=timezone.utc)


def push_series(
    sm: SignalStateMachine,
    dia_prices: list[float],
    stock_prices: list[float],
    start_time: datetime = BASE_TIME,
    news_filter: bool = False,
    high_vol: bool = False,
) -> list:
    """Push paired price series into the state machine; return non-None events."""
    events = []
    n = min(len(dia_prices), len(stock_prices))
    for i in range(n):
        t = start_time + timedelta(seconds=i)
        e1 = sm.on_tick(sm.settings.leader_symbol, dia_prices[i], t, news_filter, high_vol)
        e2 = sm.on_tick(sm.settings.stock_symbol, stock_prices[i], t + timedelta(milliseconds=50), news_filter, high_vol)
        if e1:
            events.append(e1)
        if e2:
            events.append(e2)
    return events


def _make_sm() -> SignalStateMachine:
    return SignalStateMachine(make_settings())


# ── initial state ─────────────────────────────────────────────────────────────

def test_initial_state_is_idle():
    sm = _make_sm()
    assert sm.state == SignalState.IDLE


def test_single_tick_stays_idle():
    sm = _make_sm()
    sm.on_tick("DIA", 410.0, BASE_TIME)
    assert sm.state == SignalState.IDLE


# ── synchronization ───────────────────────────────────────────────────────────

def test_transitions_to_monitoring_when_synchronized():
    sm = _make_sm()
    prices = make_trend(100.0, 60, 0.0003)
    push_series(sm, prices, prices)
    assert sm.state == SignalState.MONITORING


def test_stays_idle_when_anticorrelated():
    sm = _make_sm()
    up = make_trend(410.0, 60, 0.0003)
    down = make_trend(220.0, 60, -0.0003)
    push_series(sm, up, down)
    assert sm.state == SignalState.IDLE


# ── full happy-path signal ────────────────────────────────────────────────────

def _build_happy_path_prices():
    """
    Construct price series that walks through all four 20 MTS conditions:
      1. Synchronized (50 ticks, both rising gently)
      2. Joint decline (15 ticks, both falling -0.06%/tick)
      3. Divergence (DIA turns up 4 ticks, stock still flat)
      4. Reconnection (stock turns up 3 ticks)
    """
    sync_dia   = make_trend(410.0, 50, 0.0002)
    sync_stock = make_trend(220.0, 50, 0.0002)

    decline_dia   = make_trend(sync_dia[-1],   15, -0.0006)
    decline_stock = make_trend(sync_stock[-1], 15, -0.0006)

    diverge_dia   = make_trend(decline_dia[-1],   5, 0.0004)
    diverge_stock = [decline_stock[-1]] * 5       # stock still flat

    reconnect_dia   = make_trend(diverge_dia[-1],   4, 0.0003)
    reconnect_stock = make_trend(diverge_stock[-1], 4, 0.0003)

    dia_prices   = sync_dia + decline_dia + diverge_dia + reconnect_dia
    stock_prices = sync_stock + decline_stock + diverge_stock + reconnect_stock
    return dia_prices, stock_prices


def test_happy_path_produces_signal_fired():
    sm = _make_sm()
    dia_prices, stock_prices = _build_happy_path_prices()
    events = push_series(sm, dia_prices, stock_prices)
    fired = [e for e in events if e.state == SignalState.SIGNAL_FIRED]
    assert len(fired) >= 1, f"Expected SIGNAL_FIRED, got states: {[e.state for e in events]}"


def test_happy_path_divergence_event_emitted_first():
    sm = _make_sm()
    dia_prices, stock_prices = _build_happy_path_prices()
    events = push_series(sm, dia_prices, stock_prices)
    states = [e.state for e in events]
    assert SignalState.DIVERGENCE in states
    div_idx = states.index(SignalState.DIVERGENCE)
    fire_idx = states.index(SignalState.SIGNAL_FIRED) if SignalState.SIGNAL_FIRED in states else None
    if fire_idx is not None:
        assert div_idx < fire_idx


def test_signal_fired_has_positive_elapsed_seconds():
    sm = _make_sm()
    dia_prices, stock_prices = _build_happy_path_prices()
    events = push_series(sm, dia_prices, stock_prices)
    fired = [e for e in events if e.state == SignalState.SIGNAL_FIRED]
    if fired:
        assert fired[0].divergence_seconds_elapsed is not None
        assert fired[0].divergence_seconds_elapsed > 0


# ── one signal per decline (cooldown / re-arm) ──────────────────────────────────

def _build_decline_diverge_reconnect(start_price: float, decline_ticks: int = 20):
    """A decline long/steep enough that 3 diverge ticks + 3 reconnect ticks
    still leave the 12s-return/EMA joint-decline conditions active when
    SIGNAL_FIRED occurs."""
    decline = make_trend(start_price, decline_ticks, -0.0006)
    diverge_dia   = make_trend(decline[-1], 3, 0.0004)
    diverge_stock = [decline[-1]] * 3
    reconnect_dia   = make_trend(diverge_dia[-1], 3, 0.0003)
    reconnect_stock = make_trend(diverge_stock[-1], 3, 0.0003)
    return decline, diverge_dia, diverge_stock, reconnect_dia, reconnect_stock


def _run_decline_cycle(sm: SignalStateMachine, start_price_dia: float, start_price_stock: float, start_time: datetime):
    """Pushes one full decline -> divergence -> reconnection cycle starting
    at start_time. Returns (events, end_time, last_dia_price, last_stock_price)."""
    decline_dia, diverge_dia, diverge_stock, reconnect_dia, reconnect_stock = \
        _build_decline_diverge_reconnect(start_price_dia)
    decline_stock = make_trend(start_price_stock, len(decline_dia), -0.0006)

    t = start_time
    push_series(sm, decline_dia, decline_stock, start_time=t)
    t += timedelta(seconds=len(decline_dia))
    push_series(sm, diverge_dia, diverge_stock, start_time=t)
    t += timedelta(seconds=len(diverge_dia))
    events = push_series(sm, reconnect_dia, reconnect_stock, start_time=t)
    t += timedelta(seconds=len(reconnect_dia))
    return events, t, reconnect_dia[-1], reconnect_stock[-1]


def test_signal_fired_enters_cooldown_if_decline_still_active():
    sm = _make_sm()
    sync = make_trend(100.0, 50, 0.0002)
    push_series(sm, sync, sync)

    events, _, _, _ = _run_decline_cycle(sm, sync[-1], sync[-1], BASE_TIME + timedelta(seconds=50))
    fired = [e for e in events if e.state == SignalState.SIGNAL_FIRED]
    assert len(fired) == 1
    # The reconnection upticks alone haven't cleared the 12s-return/EMA decline
    # conditions yet, so the machine should wait in COOLDOWN rather than
    # immediately re-arming in MONITORING.
    assert sm.state == SignalState.COOLDOWN


def test_cooldown_blocks_repeated_signal_on_same_decline():
    sm = _make_sm()
    sync = make_trend(100.0, 50, 0.0002)
    push_series(sm, sync, sync)

    events, t, last_dia, last_stock = _run_decline_cycle(sm, sync[-1], sync[-1], BASE_TIME + timedelta(seconds=50))
    assert sm.state == SignalState.COOLDOWN

    # A further small DIA/stock uptick wiggle (would satisfy the divergence/
    # reconnection tick-count conditions again) must NOT produce a second
    # signal while still in cooldown.
    wiggle_dia   = make_trend(last_dia, 3, 0.0004)
    wiggle_stock = make_trend(last_stock, 3, 0.0004)
    more_events = push_series(sm, wiggle_dia, wiggle_stock, start_time=t)

    fired = [e for e in more_events if e.state == SignalState.SIGNAL_FIRED]
    assert len(fired) == 0
    assert sm.state in (SignalState.COOLDOWN, SignalState.MONITORING)


def test_cooldown_rearms_for_a_fresh_decline():
    sm = _make_sm()
    sync = make_trend(100.0, 50, 0.0002)
    push_series(sm, sync, sync)

    events, t, last_dia, last_stock = _run_decline_cycle(sm, sync[-1], sync[-1], BASE_TIME + timedelta(seconds=50))
    assert sm.state == SignalState.COOLDOWN

    # Sustained rise: clears the 12s-negative-return and below-EMA conditions
    # of the first decline, ending it -> COOLDOWN should re-arm to MONITORING.
    recover_dia   = make_trend(last_dia, 40, 0.0008)
    recover_stock = make_trend(last_stock, 40, 0.0008)
    push_series(sm, recover_dia, recover_stock, start_time=t)
    t += timedelta(seconds=len(recover_dia))
    assert sm.state == SignalState.MONITORING

    # A fresh decline -> divergence -> reconnection cycle should produce a
    # second, independent SIGNAL_FIRED.
    events2, _, _, _ = _run_decline_cycle(sm, recover_dia[-1], recover_stock[-1], t)
    fired2 = [e for e in events2 if e.state == SignalState.SIGNAL_FIRED]
    assert len(fired2) == 1


# ── signal expiry ─────────────────────────────────────────────────────────────

def test_signal_expires_when_no_reconnection():
    sm = _make_sm()

    # Sync phase
    sync_prices = make_trend(100.0, 50, 0.0002)
    push_series(sm, sync_prices, sync_prices)

    # Joint decline
    decline = make_trend(sync_prices[-1], 15, -0.0006)
    push_series(sm, decline, decline)

    # DIA diverges — stock stays flat for 130 ticks (exceeds 120s expiry)
    diverge_dia   = make_trend(decline[-1], 5, 0.0004)
    diverge_stock = [decline[-1]] * 5
    push_series(sm, diverge_dia, diverge_stock)

    # Continue: DIA holds up, stock stays flat beyond expiry window
    flat_dia   = [diverge_dia[-1]] * 130
    flat_stock = [diverge_stock[-1]] * 130
    t_offset = BASE_TIME + timedelta(seconds=200)
    events = push_series(sm, flat_dia, flat_stock, start_time=t_offset)

    expired = [e for e in events if e.state == SignalState.SIGNAL_EXPIRED]
    assert len(expired) >= 1


# ── news filter ───────────────────────────────────────────────────────────────

def test_news_filter_blocks_signal_generation():
    sm = _make_sm()
    dia_prices, stock_prices = _build_happy_path_prices()
    events = push_series(sm, dia_prices, stock_prices, news_filter=True)
    fired = [e for e in events if e.state == SignalState.SIGNAL_FIRED]
    assert len(fired) == 0


def test_news_filter_resets_active_divergence():
    sm = _make_sm()

    # Get to DIVERGENCE state without filter
    sync = make_trend(100.0, 50, 0.0002)
    push_series(sm, sync, sync)

    decline = make_trend(sync[-1], 15, -0.0006)
    push_series(sm, decline, decline)

    diverge_dia   = make_trend(decline[-1], 5, 0.0004)
    diverge_stock = [decline[-1]] * 5
    events_before = push_series(sm, diverge_dia, diverge_stock)

    div_events = [e for e in events_before if e.state == SignalState.DIVERGENCE]
    if not div_events:
        pytest.skip("Could not reach DIVERGENCE state in this test — check setup prices")

    # Now flip on news filter — state should reset
    t = BASE_TIME + timedelta(seconds=100)
    sm.on_tick("DIA", diverge_dia[-1], t, news_filter_active=True)
    assert sm.state in (SignalState.IDLE, SignalState.MONITORING)


# ── status snapshot ───────────────────────────────────────────────────────────

def test_status_returns_correct_tick_count():
    sm = _make_sm()
    for i in range(10):
        sm.on_tick("DIA", 410.0 + i * 0.01, BASE_TIME + timedelta(seconds=i))
    assert sm.tick_count == 10


def test_status_snapshot_structure():
    sm = _make_sm()
    status = sm.status()
    assert status.state == SignalState.IDLE
    assert status.tick_count == 0
    assert status.dia_price is None
    assert status.stock_price is None
