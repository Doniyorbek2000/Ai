from __future__ import annotations

from pathlib import Path

import pytest

from beauty_bot.catalog import Catalog
from beauty_bot.db import Database

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def catalog() -> Catalog:
    return Catalog.load(ROOT / "data" / "products.json")


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.connect()
    yield database
    await database.close()
