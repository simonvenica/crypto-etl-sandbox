"""Ad-hoc queries over the curated layer with DuckDB (the local stand-in for Athena)."""

from __future__ import annotations

import duckdb
import pandas as pd

from crypto_etl.config import Settings

TOP_MOVERS_SQL = """
SELECT symbol, name, price, prev_price, price_change_pct_vs_prev
FROM read_parquet(?, hive_partitioning = true)
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM read_parquet(?, hive_partitioning = true))
  AND price_change_pct_vs_prev IS NOT NULL
ORDER BY price_change_pct_vs_prev {direction}
LIMIT ?
"""


def top_movers(settings: Settings, limit: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Biggest gainers and losers on the latest snapshot date vs the previous one."""
    glob = str(settings.curated_dir / "*" / "*.parquet")
    with duckdb.connect() as con:
        gainers = con.execute(TOP_MOVERS_SQL.format(direction="DESC"), [glob, glob, limit]).df()
        losers = con.execute(TOP_MOVERS_SQL.format(direction="ASC"), [glob, glob, limit]).df()
    return gainers, losers
