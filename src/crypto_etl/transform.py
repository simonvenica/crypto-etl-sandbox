"""Transform: turn the raw API payload into a typed, clean table."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

# Column name in the API -> column name in the clean layer
COLUMN_MAP = {
    "id": "coin_id",
    "symbol": "symbol",
    "name": "name",
    "market_cap_rank": "market_cap_rank",
    "current_price": "price",
    "market_cap": "market_cap",
    "total_volume": "total_volume_24h",
    "price_change_percentage_24h": "price_change_pct_24h",
    "last_updated": "source_updated_at",
}

CLEAN_SCHEMA = {
    "coin_id": "string",
    "symbol": "string",
    "name": "string",
    "market_cap_rank": "Int64",
    "price": "float64",
    "market_cap": "float64",
    "total_volume_24h": "float64",
    "price_change_pct_24h": "float64",
    "source_updated_at": "datetime64[ns, UTC]",
    "ingested_at": "datetime64[ns, UTC]",
    "run_id": "string",
}


def to_clean(payload: list[dict], ingested_at: datetime, run_id: str) -> pd.DataFrame:
    """Select, rename and type the columns we care about. No rows are dropped here;
    validation is a separate step so bad data fails loudly instead of disappearing."""
    df = pd.DataFrame(payload)
    missing = set(COLUMN_MAP) - set(df.columns)
    if missing:
        raise ValueError(f"API payload is missing expected fields: {sorted(missing)}")

    df = df[list(COLUMN_MAP)].rename(columns=COLUMN_MAP)
    df["symbol"] = df["symbol"].str.upper()
    df["source_updated_at"] = pd.to_datetime(df["source_updated_at"], utc=True)
    df["ingested_at"] = pd.Timestamp(ingested_at).tz_convert("UTC")
    df["run_id"] = run_id

    # float64 keeps very small prices (e.g. 0.000003806) instead of rounding them to 0
    for col in ("price", "market_cap", "total_volume_24h", "price_change_pct_24h"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

    return df.astype(CLEAN_SCHEMA)[list(CLEAN_SCHEMA)]
