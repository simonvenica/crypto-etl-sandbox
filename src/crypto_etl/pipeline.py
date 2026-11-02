"""Orchestrates one run: extract -> raw -> clean (validated) -> curated."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from crypto_etl import extract, load, quality, transform
from crypto_etl.config import Settings

log = logging.getLogger(__name__)


@dataclass
class RunSummary:
    run_id: str
    raw_path: Path
    clean_path: Path
    clean_rows: int
    curated_rows: int


def run(settings: Settings, source_file: Path | None = None, now: datetime | None = None) -> RunSummary:
    ingested_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    run_id = ingested_at.strftime("%Y%m%dT%H%M%SZ")
    log.info("Run %s started", run_id)

    if source_file:
        log.info("Reading payload from %s (offline mode)", source_file)
        payload = extract.load_payload_from_file(source_file)
    else:
        payload = extract.fetch_coins_markets(settings)
    log.info("Extracted %s records", len(payload))

    # Raw is written before validation on purpose: if the checks fail,
    # the exact payload is kept for debugging and can be reprocessed later.
    raw_path = load.write_raw(payload, settings, ingested_at, run_id)

    clean_df = transform.to_clean(payload, ingested_at, run_id)
    results = quality.validate(clean_df, expected_rows=settings.top_n)
    log.info("Data quality: %s/%s checks passed", sum(r.passed for r in results), len(results))

    clean_path = load.write_clean(clean_df, settings, ingested_at, run_id)
    curated_rows = load.build_curated(settings)
    log.info("Run %s finished: %s clean rows, %s curated rows", run_id, len(clean_df), curated_rows)

    return RunSummary(run_id, raw_path, clean_path, len(clean_df), curated_rows)
