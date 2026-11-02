"""Extract: fetch the top-N coins by market cap from the CoinGecko API."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import requests

from crypto_etl.config import Settings

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def fetch_coins_markets(settings: Settings, session: requests.Session | None = None) -> list[dict]:
    """Call /coins/markets and return the JSON payload as-is.

    Retries with exponential backoff on rate limits (429) and transient server errors.
    """
    session = session or requests.Session()
    url = f"{settings.api_base_url}/coins/markets"
    params = {
        "vs_currency": settings.vs_currency,
        "order": "market_cap_desc",
        "per_page": settings.top_n,
        "page": 1,
        "price_change_percentage": "24h",
    }
    headers = {"accept": "application/json"}
    if settings.api_key:
        headers["x-cg-demo-api-key"] = settings.api_key

    for attempt in range(1, settings.max_retries + 1):
        response = session.get(url, params=params, headers=headers, timeout=settings.request_timeout_s)
        if response.status_code in RETRYABLE_STATUS and attempt < settings.max_retries:
            wait_s = int(response.headers.get("Retry-After", 2**attempt))
            log.warning("HTTP %s from CoinGecko, retrying in %ss (attempt %s)", response.status_code, wait_s, attempt)
            time.sleep(wait_s)
            continue
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError(f"Unexpected response shape: expected a list, got {type(payload).__name__}")
        return payload

    raise RuntimeError("unreachable")  # loop always returns or raises


def load_payload_from_file(path: Path) -> list[dict]:
    """Read a saved API response; used for offline runs and tests."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)
