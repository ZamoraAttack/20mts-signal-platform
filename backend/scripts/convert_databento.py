"""
Converts a Databento CSV export into the timestamp,symbol,price,volume,bid,ask
format ReplayFeed reads (see app/data_feed/replay_feed.py).

Supports Databento's documented OHLCV (e.g. ohlcv-1s), trades, and tbbo/mbp-1
schema exports, with default pretty_ts/pretty_px options. Columns are
auto-detected:
    timestamp  ts_event (ISO-8601 string, with or without "Z"/sub-microsecond
               precision, or UNIX nanoseconds as an integer)
    price      close (OHLCV schemas) or price (trades/tbbo schemas)
    volume     volume or size, if present
    bid/ask    bid_px_00 / ask_px_00, if present (tbbo/mbp-1 only)
    symbol     the file's own 'symbol' column, or --symbol to override/fill
               in for a single-symbol file that lacks one

Usage (one file per symbol):
    cd backend
    python scripts/convert_databento.py \
        --input dia_2026-06-01.csv --symbol DIA \
        --input nflx_2026-06-01.csv --symbol NFLX \
        --out data/replay_2026-06-01.csv

Usage (one combined file with its own symbol column):
    python scripts/convert_databento.py --input combined_2026-06-01.csv --out data/replay_2026-06-01.csv

By default, seconds with no trade (no row for a symbol) are forward-filled
using that symbol's last known price (volume=0) -- this matches how a
1-second chart looks when no new trade occurs (the line holds flat), which is
the view the 20 MTS strategy was developed against. Pass --no-fill-gaps to
keep only seconds where a trade actually occurred.

Verify against your actual Databento export before relying on this --
column layouts can vary slightly by schema and export options.
"""

import argparse
import csv
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

_SUBSECOND_RE = re.compile(r"(\.\d{6})\d+")


def _parse_timestamp(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    value = _SUBSECOND_RE.sub(r"\1", value)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        pass
    if value.isdigit():
        return datetime.fromtimestamp(int(value) / 1_000_000_000, tz=timezone.utc)
    raise ValueError(f"Unrecognized timestamp format: {value!r}")


def _extract_price(row: dict) -> float:
    for key in ("close", "price"):
        if row.get(key):
            return round(float(row[key]), 4)
    raise KeyError("Row has neither 'close' nor 'price' column")


def _extract_volume(row: dict) -> str:
    for key in ("volume", "size"):
        if row.get(key):
            return row[key]
    return ""


def _fill_gaps(rows: list[dict]) -> list[dict]:
    """Forward-fills missing whole seconds within each symbol's own time
    range, repeating its last known price with volume=0."""
    by_symbol: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_symbol[row["symbol"]].append(row)

    filled: list[dict] = []
    for symbol, symbol_rows in by_symbol.items():
        symbol_rows.sort(key=lambda r: r["timestamp"])
        prev_row = None
        prev_ts = None
        for row in symbol_rows:
            ts = datetime.fromisoformat(row["timestamp"])
            if prev_ts is not None:
                gap_seconds = int((ts - prev_ts).total_seconds())
                for i in range(1, gap_seconds):
                    fill_ts = prev_ts + timedelta(seconds=i)
                    filled.append({
                        "timestamp": fill_ts.isoformat(),
                        "symbol": symbol,
                        "price": prev_row["price"],
                        "volume": 0,
                        "bid": prev_row["bid"],
                        "ask": prev_row["ask"],
                    })
            filled.append(row)
            prev_row, prev_ts = row, ts
    return filled


def convert(inputs: list[tuple[str, str | None]], out_path: str, fill_gaps: bool = True) -> int:
    rows = []
    for file_path, symbol_override in inputs:
        with open(file_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                symbol = symbol_override or row.get("symbol")
                if not symbol:
                    raise ValueError(
                        f"{file_path}: row has no 'symbol' column and no --symbol override given"
                    )
                rows.append({
                    "timestamp": _parse_timestamp(row["ts_event"]).isoformat(),
                    "symbol": symbol.strip(),
                    "price": _extract_price(row),
                    "volume": _extract_volume(row),
                    "bid": row.get("bid_px_00", ""),
                    "ask": row.get("ask_px_00", ""),
                })

    if fill_gaps:
        rows = _fill_gaps(rows)

    rows.sort(key=lambda r: (r["timestamp"], r["symbol"]))

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "symbol", "price", "volume", "bid", "ask"])
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--input", action="append", required=True, dest="inputs",
        help="Path to a Databento CSV export. Repeatable for multiple files.",
    )
    parser.add_argument(
        "--symbol", action="append", default=[],
        help="Symbol override for the --input at the same position. "
             "Either give one per --input, or none at all (use each file's own 'symbol' column).",
    )
    parser.add_argument("--out", required=True, help="Output path for the ReplayFeed-format CSV")
    parser.add_argument(
        "--fill-gaps", action=argparse.BooleanOptionalAction, default=True,
        help="Forward-fill seconds with no trade per symbol (default: on)",
    )
    args = parser.parse_args()

    if args.symbol and len(args.symbol) != len(args.inputs):
        parser.error("--symbol must be given once per --input, or not at all")

    pairs = [
        (file_path, args.symbol[i] if args.symbol else None)
        for i, file_path in enumerate(args.inputs)
    ]

    count = convert(pairs, args.out, fill_gaps=args.fill_gaps)
    print(f"Wrote {count} rows to {args.out}")


if __name__ == "__main__":
    main()
