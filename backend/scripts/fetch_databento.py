"""
Pulls historical market data from Databento for a date range/symbol list and
saves it as a CSV ready for scripts/convert_databento.py.

Reads the API key from the DATABENTO_API_KEY environment variable (set it in
backend/.env -- never commit it or paste it into chat/code).

Usage:
    cd backend
    python scripts/fetch_databento.py \
        --dataset EQUS.MINI --schema ohlcv-1s \
        --symbols DIA,NFLX \
        --start 2026-06-09T13:30 --end 2026-06-09T20:00 \
        --out data/raw_2026-06-09.csv

Notes:
    - ohlcv-1s gives one row per second per symbol, matching the "1-second
      chart" model the 20 MTS strategy was developed against. If your dataset
      doesn't support ohlcv-1s, try --schema trades (one row per trade --
      convert_databento.py supports this too, but "consecutive ticks" then
      means consecutive trades rather than consecutive seconds, which is a
      different definition than the strategy was designed around).
    - start/end are UTC. Regular market hours 9:30-16:00 ET = 13:30-20:00 UTC.
    - to_csv() includes a 'symbol' column (since symbols are requested by raw
      ticker), so the output can usually be fed to convert_databento.py as a
      single --input with no --symbol override.
"""

import argparse
import os

import databento as db
from dotenv import load_dotenv

load_dotenv()


def fetch(
    dataset: str, schema: str, symbols: list[str], start: str, end: str, out_path: str,
    stype_in: str | None = None,
) -> None:
    api_key = os.environ.get("DATABENTO_API_KEY")
    if not api_key:
        raise SystemExit("Set DATABENTO_API_KEY in backend/.env first")

    client = db.Historical(api_key)
    kwargs = {}
    if stype_in:
        kwargs["stype_in"] = stype_in
    data = client.timeseries.get_range(
        dataset=dataset,
        schema=schema,
        symbols=symbols,
        start=start,
        end=end,
        **kwargs,
    )
    data.to_csv(out_path)
    print(f"Wrote {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dataset", default="EQUS.MINI")
    parser.add_argument("--schema", default="ohlcv-1s")
    parser.add_argument("--symbols", required=True, help="Comma-separated, e.g. DIA,NFLX")
    parser.add_argument("--start", required=True, help="ISO timestamp, UTC, e.g. 2026-06-09T13:30")
    parser.add_argument("--end", required=True, help="ISO timestamp, UTC, e.g. 2026-06-09T20:00")
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--stype-in", default=None,
        help="Input symbology type, e.g. 'continuous' for symbols like MYM.c.0 (futures front month)",
    )
    args = parser.parse_args()

    fetch(args.dataset, args.schema, args.symbols.split(","), args.start, args.end, args.out, args.stype_in)


if __name__ == "__main__":
    main()
