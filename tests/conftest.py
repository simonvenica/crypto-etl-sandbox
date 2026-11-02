import json
from pathlib import Path

import pytest

from crypto_etl.config import load_settings

FIXTURE = Path(__file__).parent / "fixtures" / "coins_markets_sample.json"


@pytest.fixture
def payload() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def settings(tmp_path):
    return load_settings(data_dir=tmp_path / "data", top_n=5)
