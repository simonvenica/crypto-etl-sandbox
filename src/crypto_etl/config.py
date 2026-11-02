"""Settings for the pipeline, read from environment variables with sensible defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    vs_currency: str
    top_n: int
    api_base_url: str
    api_key: str | None
    request_timeout_s: int
    max_retries: int

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw" / "coins_markets"

    @property
    def clean_dir(self) -> Path:
        return self.data_dir / "clean" / "coin_prices"

    @property
    def curated_dir(self) -> Path:
        return self.data_dir / "curated" / "daily_coin_metrics"


def load_settings(**overrides) -> Settings:
    """Build settings from the environment. Keyword overrides win over env vars."""
    values = {
        "data_dir": Path(os.getenv("CRYPTO_ETL_DATA_DIR", "data")),
        "vs_currency": os.getenv("CRYPTO_ETL_VS_CURRENCY", "usd"),
        "top_n": int(os.getenv("CRYPTO_ETL_TOP_N", "100")),
        "api_base_url": os.getenv("COINGECKO_API_BASE_URL", "https://api.coingecko.com/api/v3"),
        # Optional free "Demo" key from CoinGecko; the public endpoint also works without it.
        "api_key": os.getenv("COINGECKO_DEMO_API_KEY") or None,
        "request_timeout_s": int(os.getenv("CRYPTO_ETL_TIMEOUT_S", "30")),
        "max_retries": int(os.getenv("CRYPTO_ETL_MAX_RETRIES", "3")),
    }
    values.update({k: v for k, v in overrides.items() if v is not None})
    values["data_dir"] = Path(values["data_dir"])
    if not 1 <= values["top_n"] <= 250:
        raise ValueError("top_n must be between 1 and 250 (CoinGecko page size limit)")
    return Settings(**values)
