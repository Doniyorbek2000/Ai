import json


def test_catalog_loads_and_ids_unique(catalog):
    ids = [p.id for p in catalog.products]
    assert len(ids) == len(set(ids)) >= 20
    for p in catalog.products:
        assert p.category in catalog.categories
        assert p.price > 0
        assert p.name["uz"] and p.name["ru"]


def test_every_category_has_products(catalog):
    for c in catalog.categories:
        assert catalog.available(c), c


def test_valid_ids_filters_unknown_duplicates_and_limits(catalog):
    got = catalog.valid_ids(["sk-spf50", "nope", "sk-spf50", "sk-niacinamide"])
    assert [p.id for p in got] == ["sk-spf50", "sk-niacinamide"]
    many = catalog.valid_ids([p.id for p in catalog.products], limit=3)
    assert len(many) == 3


def test_ai_context_is_compact_json_for_requested_categories(catalog):
    rows = json.loads(catalog.ai_context(("perfume",)))
    assert rows and all(r["category"] == "perfume" for r in rows)
    assert all("families" in r for r in rows)


def test_localized_titles(catalog):
    p = catalog.get("sk-spf50")
    assert p.title("ru").startswith("Солнцезащитный")
    assert p.title("uz_cyrl").startswith("Қуёшдан")
