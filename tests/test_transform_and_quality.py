from datetime import datetime, timezone

import pytest

from crypto_etl.quality import DataQualityError, validate
from crypto_etl.transform import CLEAN_SCHEMA, to_clean

NOW = datetime(2026, 1, 1, 12, 5, tzinfo=timezone.utc)


def test_clean_has_expected_schema(payload):
    df = to_clean(payload, NOW, "run1")
    assert list(df.columns) == list(CLEAN_SCHEMA)
    assert df["symbol"].tolist()[:2] == ["BTC", "ETH"]


def test_tiny_prices_are_kept(payload):
    df = to_clean(payload, NOW, "run1")
    pepe = df.loc[df["coin_id"] == "pepe", "price"].item()
    assert pepe == pytest.approx(0.000003806)


def test_missing_field_fails_fast(payload):
    for row in payload:
        del row["current_price"]
    with pytest.raises(ValueError, match="current_price"):
        to_clean(payload, NOW, "run1")


def test_valid_data_passes_all_checks(payload):
    df = to_clean(payload, NOW, "run1")
    results = validate(df, expected_rows=5)
    assert all(r.passed for r in results)


@pytest.mark.parametrize(
    "mutate, failing_check",
    [
        (lambda p: p.append(dict(p[0])), "coin_id_unique"),
        (lambda p: p[1].update(current_price=-1), "price_non_negative"),
        (lambda p: p[2].update(id=None), "required_not_null"),
        (lambda p: p.pop(), "row_count"),
    ],
)
def test_bad_data_is_rejected(payload, mutate, failing_check):
    mutate(payload)
    df = to_clean(payload, NOW, "run1")
    with pytest.raises(DataQualityError, match=failing_check):
        validate(df, expected_rows=5)
