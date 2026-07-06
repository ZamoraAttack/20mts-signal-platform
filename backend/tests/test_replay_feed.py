import csv
from datetime import date

import pytest

from app.data_feed.replay_feed import ReplayFeed

FIELDS = ["timestamp", "symbol", "price", "volume", "bid", "ask"]


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def row(timestamp, symbol, price, volume="", bid="", ask=""):
    return {"timestamp": timestamp, "symbol": symbol, "price": price, "volume": volume, "bid": bid, "ask": ask}


@pytest.mark.asyncio
async def test_connect_loads_and_sorts_ticks(tmp_path):
    csv_path = tmp_path / "replay.csv"
    write_csv(csv_path, [
        row("2025-03-17T09:30:01-04:00", "AAPL", "220.1"),
        row("2025-03-17T09:30:00-04:00", "DIA", "410.0", volume="1000", bid="409.9", ask="410.1"),
        row("2025-03-17T09:30:00-04:00", "AAPL", "220.0"),
    ])

    feed = ReplayFeed(str(csv_path))
    await feed.connect()

    assert [t.symbol for t in feed._ticks] == ["DIA", "AAPL", "AAPL"]
    assert feed._ticks[0].volume == 1000
    assert feed._ticks[0].bid == 409.9
    assert feed._ticks[0].ask == 410.1


@pytest.mark.asyncio
async def test_session_date_derived_from_first_tick_et(tmp_path):
    csv_path = tmp_path / "replay.csv"
    write_csv(csv_path, [
        row("2025-03-17T09:30:00-04:00", "DIA", "410.0"),
    ])
    feed = ReplayFeed(str(csv_path))
    await feed.connect()
    assert feed.session_date == date(2025, 3, 17)


@pytest.mark.asyncio
async def test_stream_filters_to_subscribed_symbols(tmp_path):
    csv_path = tmp_path / "replay.csv"
    write_csv(csv_path, [
        row("2025-03-17T09:30:00-04:00", "DIA", "410.0"),
        row("2025-03-17T09:30:00-04:00", "MSFT", "300.0"),
        row("2025-03-17T09:30:01-04:00", "DIA", "410.5"),
    ])
    feed = ReplayFeed(str(csv_path))
    await feed.connect()
    await feed.subscribe(["DIA"])

    ticks = [t async for t in feed.stream()]
    assert [t.symbol for t in ticks] == ["DIA", "DIA"]
    assert ticks[1].price == 410.5


@pytest.mark.asyncio
async def test_speed_zero_streams_without_delay(tmp_path):
    csv_path = tmp_path / "replay.csv"
    write_csv(csv_path, [
        row("2025-03-17T09:30:00-04:00", "DIA", "410.0"),
        row("2025-03-17T09:35:00-04:00", "DIA", "411.0"),
    ])
    feed = ReplayFeed(str(csv_path), speed=0.0)
    await feed.connect()
    await feed.subscribe(["DIA"])

    ticks = []
    async for t in feed.stream():
        ticks.append(t)

    assert len(ticks) == 2
    assert ticks[1].price == 411.0
