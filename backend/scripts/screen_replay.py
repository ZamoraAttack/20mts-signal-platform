"""
Headless backtest runner: replays a CSV (same format ReplayFeed reads)
directly through SignalStateMachine -- no database, no API, no uvicorn -- so
many days can be screened quickly for correlation and signal activity.

Usage:
    cd backend
    python scripts/screen_replay.py data/replay_2026-06-10.csv --stock-symbol NFLX
"""

import argparse
import csv
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings
from app.signal_engine.state_machine import SignalState, SignalStateMachine

ET = ZoneInfo("America/New_York")


def screen(file_path: str, leader_symbol: str, stock_symbol: str):
    settings = Settings(leader_symbol=leader_symbol, stock_symbol=stock_symbol)
    machine = SignalStateMachine(settings)

    with open(file_path, newline="") as f:
        reader = csv.DictReader(f)
        rows = sorted(reader, key=lambda r: r["timestamp"])

    max_corr = None
    events = []
    state_counts: Counter[SignalState] = Counter()
    for row in rows:
        symbol = row["symbol"].strip()
        if symbol not in (leader_symbol, stock_symbol):
            continue
        price = float(row["price"])
        ts = datetime.fromisoformat(row["timestamp"])
        event = machine.on_tick(symbol, price, ts)

        status = machine.status()
        if status.correlation is not None:
            if max_corr is None or status.correlation > max_corr:
                max_corr = status.correlation

        state_counts[machine.state] += 1

        if event is not None:
            events.append(event)

    return machine.tick_count, max_corr, machine.status().state, events, state_counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file", help="Path to a ReplayFeed-format CSV")
    parser.add_argument("--leader-symbol", default="DIA")
    parser.add_argument("--stock-symbol", required=True)
    args = parser.parse_args()

    tick_count, max_corr, final_state, events, state_counts = screen(args.file, args.leader_symbol, args.stock_symbol)

    print(f"{args.file}: {args.leader_symbol} vs {args.stock_symbol}")
    print(f"  ticks processed: {tick_count}")
    print(f"  max correlation: {max_corr:.3f}" if max_corr is not None else "  max correlation: n/a")
    print(f"  final state: {final_state.value}")
    print("  ticks spent in each state:")
    for state in SignalState:
        count = state_counts.get(state, 0)
        if count:
            print(f"    {state.value:<15} {count}")
    if not events:
        print("  signal events: none")
    else:
        print(f"  signal events ({len(events)}):")
        for e in events:
            ts_et = e.timestamp.astimezone(ET).strftime("%H:%M:%S")
            print(f"    {ts_et} ET  {e.state.value:<15}  {e.notes}")


if __name__ == "__main__":
    main()
