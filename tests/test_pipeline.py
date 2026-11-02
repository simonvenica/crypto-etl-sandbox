import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from crypto_etl import pipeline, report
from crypto_etl.quality import DataQualityError

FIXTURE = Path(__file__).parent / "fixtures" / "coins_markets_sample.json"


def _write_day(tmp_path, payload, btc_price, name):
    payload = [dict(row) for row in payload]
    payload[0]["current_price"] = btc_price
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_end_to_end_two_days(tmp_path, payload, settings):
    day1 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    day2_early = datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc)
    day2_late = datetime(2026, 1, 2, 18, 0, tzinfo=timezone.utc)

    pipeline.run(settings, source_file=FIXTURE, now=day1)                                      # BTC 68000
    pipeline.run(settings, source_file=_write_day(tmp_path, payload, 1.0, "a.json"), now=day2_early)  # overwritten later
    summary = pipeline.run(settings, source_file=_write_day(tmp_path, payload, 71400.0, "b.json"), now=day2_late)

    # every layer was written, partitioned by date
    assert summary.raw_path.exists() and "ingestion_date=2026-01-02" in str(summary.raw_path)
    assert len(list(settings.clean_dir.glob("*/*.parquet"))) == 3

    curated = pd.read_parquet(settings.curated_dir)
    assert len(curated) == 10  # 5 coins x 2 days: the early run on day 2 is deduplicated
    assert summary.curated_rows == 10

    btc_day2 = curated[(curated["coin_id"] == "bitcoin") & (curated["snapshot_date"].astype(str) == "2026-01-02")]
    assert btc_day2["price"].item() == 71400.0          # latest run of the day wins
    assert btc_day2["price_change_pct_vs_prev"].item() == pytest.approx(5.0)

    gainers, losers = report.top_movers(settings, limit=1)
    assert gainers["symbol"].tolist() == ["BTC"]


def test_rerun_is_idempotent(payload, settings):
    when = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    first = pipeline.run(settings, source_file=FIXTURE, now=when)
    second = pipeline.run(settings, source_file=FIXTURE, now=when)
    assert first.curated_rows == second.curated_rows == 5


def test_failed_quality_keeps_raw_but_writes_nothing_else(tmp_path, payload, settings):
    payload[1]["current_price"] = -10
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DataQualityError):
        pipeline.run(settings, source_file=bad, now=datetime(2026, 1, 1, tzinfo=timezone.utc))

    assert len(list(settings.raw_dir.glob("*/*.json"))) == 1
    assert not settings.clean_dir.exists()
    assert not settings.curated_dir.exists()
