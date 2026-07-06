import csv

import pytest

from app.data_feed.replay_feed import ReplayFeed
from scripts.convert_databento import convert


def write_csv(path, fieldnames, rows):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_output(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def test_converts_ohlcv_with_iso_z_timestamps(tmp_path):
    src = tmp_path / "dia_ohlcv.csv"
    write_csv(src, ["ts_event", "open", "high", "low", "close", "volume", "symbol"], [
        {"ts_event": "2025-03-17T13:30:00.123456789Z", "open": "410.0", "high": "410.2",
         "low": "409.9", "close": "410.1", "volume": "1000", "symbol": "DIA"},
        {"ts_event": "2025-03-17T13:30:01Z", "open": "410.1", "high": "410.3",
         "low": "410.0", "close": "410.2", "volume": "1100", "symbol": "DIA"},
    ])
    out = tmp_path / "out.csv"

    count = convert([(str(src), None)], str(out))

    assert count == 2
    rows = read_output(out)
    assert rows[0]["timestamp"] == "2025-03-17T13:30:00.123456+00:00"
    assert rows[0]["symbol"] == "DIA"
    assert rows[0]["price"] == "410.1"
    assert rows[0]["volume"] == "1000"
    assert rows[1]["timestamp"] == "2025-03-17T13:30:01+00:00"


def test_converts_tbbo_with_nanosecond_timestamps_and_symbol_override(tmp_path):
    src = tmp_path / "nflx_tbbo.csv"
    write_csv(src, ["ts_event", "price", "size", "bid_px_00", "ask_px_00"], [
        {"ts_event": "1742218200000000000", "price": "950.123456", "size": "50",
         "bid_px_00": "950.10", "ask_px_00": "950.15"},
    ])
    out = tmp_path / "out.csv"

    count = convert([(str(src), "NFLX")], str(out))

    assert count == 1
    rows = read_output(out)
    assert rows[0]["symbol"] == "NFLX"
    assert rows[0]["price"] == "950.1235"
    assert rows[0]["volume"] == "50"
    assert rows[0]["bid"] == "950.10"
    assert rows[0]["ask"] == "950.15"


def test_merges_and_sorts_multiple_input_files(tmp_path):
    dia = tmp_path / "dia.csv"
    nflx = tmp_path / "nflx.csv"
    write_csv(dia, ["ts_event", "close", "volume"], [
        {"ts_event": "2025-03-17T13:30:01Z", "close": "410.2", "volume": "1100"},
        {"ts_event": "2025-03-17T13:30:00Z", "close": "410.1", "volume": "1000"},
    ])
    write_csv(nflx, ["ts_event", "close", "volume"], [
        {"ts_event": "2025-03-17T13:30:00Z", "close": "950.0", "volume": "50"},
    ])
    out = tmp_path / "out.csv"

    count = convert([(str(dia), "DIA"), (str(nflx), "NFLX")], str(out))

    assert count == 3
    rows = read_output(out)
    assert [(r["timestamp"], r["symbol"]) for r in rows] == [
        ("2025-03-17T13:30:00+00:00", "DIA"),
        ("2025-03-17T13:30:00+00:00", "NFLX"),
        ("2025-03-17T13:30:01+00:00", "DIA"),
    ]


def test_missing_symbol_without_override_raises(tmp_path):
    src = tmp_path / "no_symbol.csv"
    write_csv(src, ["ts_event", "close"], [
        {"ts_event": "2025-03-17T13:30:00Z", "close": "410.1"},
    ])
    out = tmp_path / "out.csv"

    with pytest.raises(ValueError, match="no 'symbol' column"):
        convert([(str(src), None)], str(out))


def test_fills_gaps_with_forward_fill_by_default(tmp_path):
    src = tmp_path / "dia.csv"
    write_csv(src, ["ts_event", "close", "volume"], [
        {"ts_event": "2025-03-17T13:30:00Z", "close": "410.0", "volume": "100"},
        {"ts_event": "2025-03-17T13:30:03Z", "close": "410.5", "volume": "200"},
    ])
    out = tmp_path / "out.csv"

    count = convert([(str(src), "DIA")], str(out))

    assert count == 4
    rows = read_output(out)
    assert [r["timestamp"] for r in rows] == [
        "2025-03-17T13:30:00+00:00",
        "2025-03-17T13:30:01+00:00",
        "2025-03-17T13:30:02+00:00",
        "2025-03-17T13:30:03+00:00",
    ]
    assert rows[1]["price"] == "410.0"
    assert rows[1]["volume"] == "0"
    assert rows[2]["price"] == "410.0"
    assert rows[2]["volume"] == "0"
    assert rows[3]["price"] == "410.5"


def test_fill_gaps_false_leaves_gaps(tmp_path):
    src = tmp_path / "dia.csv"
    write_csv(src, ["ts_event", "close", "volume"], [
        {"ts_event": "2025-03-17T13:30:00Z", "close": "410.0", "volume": "100"},
        {"ts_event": "2025-03-17T13:30:03Z", "close": "410.5", "volume": "200"},
    ])
    out = tmp_path / "out.csv"

    count = convert([(str(src), "DIA")], str(out), fill_gaps=False)

    assert count == 2


@pytest.mark.asyncio
async def test_output_round_trips_through_replay_feed(tmp_path):
    dia = tmp_path / "dia.csv"
    nflx = tmp_path / "nflx.csv"
    write_csv(dia, ["ts_event", "close", "volume"], [
        {"ts_event": "2025-03-17T13:30:00Z", "close": "410.1", "volume": "1000"},
        {"ts_event": "2025-03-17T13:30:01Z", "close": "410.2", "volume": "1100"},
    ])
    write_csv(nflx, ["ts_event", "close", "volume"], [
        {"ts_event": "2025-03-17T13:30:00Z", "close": "950.0", "volume": "50"},
        {"ts_event": "2025-03-17T13:30:01Z", "close": "950.5", "volume": "60"},
    ])
    out = tmp_path / "replay_2025-03-17.csv"
    convert([(str(dia), "DIA"), (str(nflx), "NFLX")], str(out))

    feed = ReplayFeed(str(out))
    await feed.connect()

    assert len(feed._ticks) == 4
    assert feed.session_date.isoformat() == "2025-03-17"
    assert {t.symbol for t in feed._ticks} == {"DIA", "NFLX"}
