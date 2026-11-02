"""Data quality checks on the clean table. Any failure stops the run before data is written."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from crypto_etl.transform import CLEAN_SCHEMA


class DataQualityError(Exception):
    """Raised when one or more checks fail."""


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


def run_checks(df: pd.DataFrame, expected_rows: int) -> list[CheckResult]:
    results = [
        CheckResult(
            "schema",
            list(df.columns) == list(CLEAN_SCHEMA)
            and all(str(df[c].dtype) == t for c, t in CLEAN_SCHEMA.items()),
            f"columns={list(df.columns)}",
        ),
        CheckResult("row_count", len(df) == expected_rows, f"expected {expected_rows}, got {len(df)}"),
        CheckResult(
            "required_not_null",
            not df[["coin_id", "symbol", "name", "price"]].isna().any().any(),
            df[["coin_id", "symbol", "name", "price"]].isna().sum().to_dict().__repr__(),
        ),
        CheckResult(
            "coin_id_unique",
            df["coin_id"].is_unique,
            f"duplicates={df.loc[df['coin_id'].duplicated(), 'coin_id'].tolist()}",
        ),
        CheckResult(
            "price_non_negative",
            bool((df["price"].dropna() >= 0).all()),
            f"negative={df.loc[df['price'] < 0, 'coin_id'].tolist()}",
        ),
        CheckResult(
            "market_cap_non_negative",
            bool((df["market_cap"].dropna() >= 0).all()),
            f"negative={df.loc[df['market_cap'] < 0, 'coin_id'].tolist()}",
        ),
    ]
    return results


def validate(df: pd.DataFrame, expected_rows: int) -> list[CheckResult]:
    results = run_checks(df, expected_rows)
    failed = [r for r in results if not r.passed]
    if failed:
        lines = "\n".join(f"  - {r.name}: {r.detail}" for r in failed)
        raise DataQualityError(f"{len(failed)} data quality check(s) failed:\n{lines}")
    return results
