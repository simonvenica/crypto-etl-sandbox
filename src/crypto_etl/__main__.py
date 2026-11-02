"""Command line entry point.

    python -m crypto_etl run                      # call the API
    python -m crypto_etl run --source-file x.json # offline, from a saved response
    python -m crypto_etl report                   # top movers from the curated layer
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from crypto_etl import pipeline, report
from crypto_etl.config import load_settings
from crypto_etl.quality import DataQualityError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="crypto_etl")
    parser.add_argument("--data-dir", type=Path, help="where the layers are stored (default: ./data)")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="run the pipeline once")
    run_p.add_argument("--top-n", type=int, help="number of coins to fetch (default: 100)")
    run_p.add_argument("--source-file", type=Path, help="use a saved API response instead of calling the API")

    rep_p = sub.add_parser("report", help="show top movers from the curated layer")
    rep_p.add_argument("--limit", type=int, default=5)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    settings = load_settings(data_dir=args.data_dir, top_n=getattr(args, "top_n", None))

    if args.command == "run":
        try:
            summary = pipeline.run(settings, source_file=args.source_file)
        except DataQualityError as e:
            logging.error("%s", e)
            return 1
        print(f"OK run_id={summary.run_id} clean_rows={summary.clean_rows} curated_rows={summary.curated_rows}")
        return 0

    gainers, losers = report.top_movers(settings, limit=args.limit)
    if gainers.empty:
        print("Not enough history yet: at least two days of data are needed to compare prices.")
        return 0
    print("Top gainers vs previous snapshot:\n", gainers.to_string(index=False), "\n", sep="")
    print("Top losers vs previous snapshot:\n", losers.to_string(index=False), sep="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
