# crypto-etl-sandbox

A small practice project: a batch ETL that takes the top cryptocurrencies by market cap
from the [CoinGecko API](https://www.coingecko.com/en/api) and stores them in
raw / clean / curated layers as date-partitioned Parquet, queried with DuckDB.

It is a sandbox for trying out a few data engineering patterns on a tiny dataset,
not a production system. The scheduled run is intentionally disabled (see below).

## What it does

```
CoinGecko /coins/markets
        │
        ▼
 raw      data/raw/coins_markets/ingestion_date=YYYY-MM-DD/<run_id>.json
          exact API response, kept so any run can be replayed
        │  rename + type columns
        ▼
 checks   schema, row count, nulls, unique ids, non-negative values
          any failure stops the run before clean/curated are touched
        │
        ▼
 clean    data/clean/coin_prices/ingestion_date=YYYY-MM-DD/<run_id>.parquet
        │  DuckDB SQL: latest snapshot per coin per day + change vs previous day
        ▼
 curated  data/curated/daily_coin_metrics/snapshot_date=YYYY-MM-DD/*.parquet
```

Patterns it practices:

- **Layered storage** (raw → clean → curated) with Hive-style partitions, the same layout
  S3 + Glue/Athena expect, so the local folders map 1:1 to a bucket.
- **Data quality gate** between extract and load.
- **Idempotent runs**: the curated layer is rebuilt from the clean layer and swapped in only
  after it is fully written; re-running the same day gives the same result.
- **Retries with backoff** on API rate limits.

## Run it locally

Requires Python 3.11+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest                                   # tests use a saved sample, no network
python -m crypto_etl run                 # one run against the live API
python -m crypto_etl report              # top movers (needs at least two days of data)
```

Offline run with the sample response:

```bash
python -m crypto_etl run --top-n 5 --source-file tests/fixtures/coins_markets_sample.json
```

Settings are optional environment variables, listed in [`.env.example`](.env.example).
A free CoinGecko Demo key raises the rate limit but is not required.

## Scheduling

[`.github/workflows/pipeline.yml`](.github/workflows/pipeline.yml) runs tests and the pipeline on
GitHub Actions and uploads the data folder as an artifact. It only has a manual trigger;
the daily `schedule` is commented out so the repo does not consume Actions minutes on its own.

## Project layout

```
src/crypto_etl/
  extract.py    API client with retries
  transform.py  raw payload -> typed clean table
  quality.py    data quality checks
  load.py       writes raw/clean, builds curated with DuckDB
  pipeline.py   one end-to-end run
  report.py     example query over the curated layer
tests/          unit + end-to-end tests with a sample payload
```

## License

MIT
