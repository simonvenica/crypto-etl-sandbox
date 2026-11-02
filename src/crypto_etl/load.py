"""Load: write each layer to disk.

Layout (Hive-style partitions, the same convention S3 + Athena/Glue use):

    data/raw/coins_markets/ingestion_date=YYYY-MM-DD/<run_id>.json
    data/clean/coin_prices/ingestion_date=YYYY-MM-DD/<run_id>.parquet
    data/curated/daily_coin_metrics/snapshot_date=YYYY-MM-DD/data_0.parquet
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

from crypto_etl.config import Settings


def write_raw(payload: list[dict], settings: Settings, ingested_at: datetime, run_id: str) -> Path:
    """Store the API response untouched, so any later step can be replayed from it."""
    path = settings.raw_dir / f"ingestion_date={ingested_at:%Y-%m-%d}" / f"{run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    return path


def write_clean(df: pd.DataFrame, settings: Settings, ingested_at: datetime, run_id: str) -> Path:
    path = settings.clean_dir / f"ingestion_date={ingested_at:%Y-%m-%d}" / f"{run_id}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path


CURATED_SQL = """
WITH ranked AS (
    -- several runs on the same day: keep the latest snapshot per coin
    SELECT
        *,
        CAST(ingested_at AS DATE) AS snapshot_date,
        ROW_NUMBER() OVER (
            PARTITION BY coin_id, CAST(ingested_at AS DATE)
            ORDER BY ingested_at DESC
        ) AS rn
    FROM read_parquet(?, hive_partitioning = true)
),
daily AS (
    SELECT snapshot_date, coin_id, symbol, name, market_cap_rank,
           price, market_cap, total_volume_24h, ingested_at
    FROM ranked
    WHERE rn = 1
)
SELECT
    snapshot_date,
    coin_id,
    symbol,
    name,
    market_cap_rank,
    price,
    market_cap,
    total_volume_24h,
    LAG(price) OVER w AS prev_price,
    LAG(snapshot_date) OVER w AS prev_snapshot_date,
    ROUND(100 * (price / NULLIF(LAG(price) OVER w, 0) - 1), 4) AS price_change_pct_vs_prev,
    ingested_at AS last_ingested_at
FROM daily
WINDOW w AS (PARTITION BY coin_id ORDER BY snapshot_date)
ORDER BY snapshot_date, market_cap_rank
"""


def build_curated(settings: Settings) -> int:
    """Rebuild the curated table from the whole clean layer.

    The data is tiny (100 rows per run), so a full rebuild is simpler and safer
    than incremental merges, and it makes the step idempotent.
    Returns the number of rows written.
    """
    clean_glob = str(settings.clean_dir / "*" / "*.parquet")
    tmp_dir = settings.curated_dir.with_name(settings.curated_dir.name + "_tmp")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    tmp_dir.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect() as con:
        con.execute(f"CREATE TABLE curated AS {CURATED_SQL}", [clean_glob])
        rows = con.execute("SELECT COUNT(*) FROM curated").fetchone()[0]
        con.execute(
            "COPY curated TO ? (FORMAT parquet, PARTITION_BY (snapshot_date))",
            [str(tmp_dir)],
        )

    # swap only after the new version was fully written
    shutil.rmtree(settings.curated_dir, ignore_errors=True)
    tmp_dir.rename(settings.curated_dir)
    return rows
