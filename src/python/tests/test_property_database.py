# Tests for property_database.py — SQLite-backed property store and search tool.

import json

import pytest
from property_database import Property, PropertyDatabase


def _sample(pid, **overrides):
    """Builds a property JSON dict matching the seed schema."""
    data = {
        "id": pid,
        "type": "Detached",
        "status": "For Sale",
        "price": 500000,
        "currency": "CAD",
        "address": {
            "street": f"{pid} Main St",
            "city": "Toronto",
            "province": "ON",
            "postalCode": "M1M1M1",
            "country": "Canada",
        },
        "bedrooms": 3,
        "bathrooms": 2,
        "squareFootage": 1500,
        "lotSizeSquareFootage": 3000,
        "yearBuilt": 2000,
        "parkingSpaces": 1,
        "shortDescription": "Nice home",
        "fullDescription": "A very nice home",
        "keyFeatures": ["backyard", "garage"],
        "listedDate": "2024-01-01",
    }
    data.update(overrides)
    return data


@pytest.fixture
async def seeded_db(tmp_path):
    """A PropertyDatabase seeded from JSON files in a temp directory."""
    data_dir = tmp_path / "Properties"
    data_dir.mkdir()

    props = [
        _sample(1, address={**_sample(1)["address"], "city": "Toronto"}, price=400000, bedrooms=2),
        _sample(2, address={**_sample(2)["address"], "city": "Vancouver"}, price=800000, bedrooms=4,
                type="Condo", parkingSpaces=2, bathrooms=3, squareFootage=2500),
        _sample(3, lotSizeSquareFootage=None),  # exercises the nullable lot size branch
    ]
    for p in props:
        (data_dir / f"{p['id']:05d}.json").write_text(json.dumps(p), encoding="utf-8")

    db = PropertyDatabase(db_path=str(tmp_path / "test.db"))
    await db.initialize()
    await db.seed_data(str(data_dir))
    return db


def test_to_dict_with_list_key_features():
    prop = Property(
        id=1, type="Detached", status="For Sale", price=100, currency="CAD",
        address_street="1 A St", address_city="Toronto", address_province="ON",
        address_postal_code="M1", address_country="Canada", bedrooms=3, bathrooms=2,
        square_footage=1500, lot_size_square_footage=None, year_built=2000,
        parking_spaces=1, short_description="s", full_description="f",
        key_features=["a", "b"], listed_date="2024-01-01",
    )
    d = prop.to_dict()
    assert d["address"]["city"] == "Toronto"
    assert d["keyFeatures"] == ["a", "b"]
    assert d["lotSizeSquareFootage"] is None


def test_to_dict_with_json_string_key_features():
    prop = Property(
        id=2, type="Condo", status="For Sale", price=100, currency="CAD",
        address_street="2 B St", address_city="Vancouver", address_province="BC",
        address_postal_code="V1", address_country="Canada", bedrooms=2, bathrooms=1,
        square_footage=900, lot_size_square_footage=1000, year_built=2010,
        parking_spaces=0, short_description="s", full_description="f",
        key_features=json.dumps(["x", "y"]), listed_date="2024-02-02",
    )
    d = prop.to_dict()
    assert d["keyFeatures"] == ["x", "y"]


async def test_search_no_filters_returns_all(seeded_db):
    results = await seeded_db.search()
    assert len(results) == 3


async def test_search_by_city_is_case_insensitive(seeded_db):
    results = await seeded_db.search(city="toronto")
    assert all(r["address"]["city"] == "Toronto" for r in results)
    assert len(results) >= 1


async def test_search_by_property_type(seeded_db):
    results = await seeded_db.search(property_type="condo")
    assert len(results) == 1
    assert results[0]["type"] == "Condo"


async def test_search_bedroom_and_price_range(seeded_db):
    results = await seeded_db.search(min_bedrooms=4, min_price=500000, max_price=900000)
    assert len(results) == 1
    assert results[0]["bedrooms"] == 4


async def test_search_all_numeric_filters(seeded_db):
    results = await seeded_db.search(
        min_bedrooms=1, max_bedrooms=5, min_bathrooms=1, max_bathrooms=5,
        min_price=1, max_price=10_000_000, min_square_footage=100,
        max_square_footage=10_000, min_parking=0,
    )
    assert len(results) == 3


async def test_search_no_results(seeded_db):
    results = await seeded_db.search(city="Nowhere")
    assert results == []


async def test_seed_is_idempotent(seeded_db, tmp_path):
    # Seeding again must not duplicate rows (hits the "already seeded" branch).
    await seeded_db.seed_data(str(tmp_path / "Properties"))
    results = await seeded_db.search()
    assert len(results) == 3


async def test_seed_missing_directory_is_safe(tmp_path):
    db = PropertyDatabase(db_path=str(tmp_path / "empty.db"))
    await db.initialize()
    await db.seed_data(str(tmp_path / "does_not_exist"))
    results = await db.search()
    assert results == []
