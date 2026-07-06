"""
Generates a synthetic historical replay CSV for exercising ReplayFeed
end-to-end before real historical 1-second data is available.

Uses the same correlated common-shock random-walk model as SimulatedFeed,
but with timestamps starting at 9:30:00 ET on a given date instead of "now",
so the output can be loaded by ReplayFeed and shows up as a normal session
on the given date.

Usage:
    cd backend
    python scripts/generate_sample_replay.py --date 2025-03-17 --minutes 30
"""

import argparse
import csv
import math
import os
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def generate(
    date_str: str,
    minutes: int,
    leader_symbol: str,
    stock_symbol: str,
    correlation: float,
    seed: int,
    out_path: str,
) -> None:
    random.seed(seed)
    start = datetime.strptime(date_str, "%Y-%m-%d").replace(
        hour=9, minute=30, second=0, microsecond=0, tzinfo=ET
    )
    prices = {leader_symbol: 410.00, stock_symbol: 220.00}

    rows = []
    for i in range(minutes * 60):
        ts = start + timedelta(seconds=i)
        common_shock = random.gauss(0, 0.0002)
        for sym in (leader_symbol, stock_symbol):
            idio = random.gauss(0, 0.0001)
            if sym == leader_symbol:
                ret = common_shock + idio
            else:
                ret = (
                    correlation * common_shock
                    + math.sqrt(max(0.0, 1 - correlation ** 2)) * idio
                )
            prices[sym] *= 1 + ret
            rows.append({
                "timestamp": ts.isoformat(),
                "symbol": sym,
                "price": round(prices[sym], 4),
                "volume": "",
                "bid": "",
                "ask": "",
            })

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "symbol", "price", "volume", "bid", "ask"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows ({minutes} minutes x 2 symbols) to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="Session date, YYYY-MM-DD (ET)")
    parser.add_argument("--minutes", type=int, default=30, help="Minutes of 1s data per symbol")
    parser.add_argument("--leader-symbol", default="DIA")
    parser.add_argument("--stock-symbol", default="AAPL")
    parser.add_argument("--correlation", type=float, default=0.85)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", default="data/sample_replay.csv")
    args = parser.parse_args()

    generate(
        args.date, args.minutes, args.leader_symbol, args.stock_symbol,
        args.correlation, args.seed, args.out,
    )


if __name__ == "__main__":
    main()
