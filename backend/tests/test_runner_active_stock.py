import pytest

from app.data_feed import FeedManager, SimulatedFeed
from app.engine.runner import EngineRunner
from app.engine.symbol_validation import InvalidSymbolError
from app.signal_engine import SignalStateMachine
from tests.conftest import make_settings


def _make_runner(**settings_overrides) -> EngineRunner:
    defaults = dict(leader_symbol="DIA", stock_symbol="NFLX", watchlist_symbols="AAPL,META")
    defaults.update(settings_overrides)
    settings = make_settings(**defaults)
    feed_manager = FeedManager(SimulatedFeed(seed=1))
    return EngineRunner(feed_manager, settings)


@pytest.mark.asyncio
async def test_promotes_symbol_present_in_watchlist():
    runner = _make_runner()
    original_state_machine = runner.state_machine

    await runner.set_active_stock("AAPL")

    assert runner.settings.stock_symbol == "AAPL"
    assert runner.state_machine is not original_state_machine  # fresh, reset state machine


@pytest.mark.asyncio
async def test_rejects_symbol_not_in_watchlist_and_leaves_state_untouched():
    runner = _make_runner()
    original_state_machine = runner.state_machine

    with pytest.raises(InvalidSymbolError, match="not in the current watchlist"):
        await runner.set_active_stock("ZZZZ")

    assert runner.settings.stock_symbol == "NFLX"  # unchanged
    assert runner.state_machine is original_state_machine  # not reset


@pytest.mark.asyncio
async def test_rejects_empty_symbol_and_leaves_state_untouched():
    runner = _make_runner()

    with pytest.raises(InvalidSymbolError, match="empty"):
        await runner.set_active_stock("")

    assert runner.settings.stock_symbol == "NFLX"


@pytest.mark.asyncio
async def test_rejects_malformed_symbol_even_if_in_watchlist_string():
    runner = _make_runner(watchlist_symbols="AAPL,NF1X!")

    with pytest.raises(InvalidSymbolError, match="well-formed"):
        await runner.set_active_stock("NF1X!")

    assert runner.settings.stock_symbol == "NFLX"
