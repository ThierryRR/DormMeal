from pathlib import Path

import pytest

from dormmeal.db import fetch_catalog, import_catalog, init_db
from dormmeal.tools import load_catalog_csv

CSV = Path(__file__).resolve().parent.parent / "data" / "catalog_v1.csv"


@pytest.fixture(scope="module")
def catalog():
    return load_catalog_csv(CSV)


def test_catalog_size(catalog):
    assert len(catalog) >= 50


def test_ids_unique(catalog):
    ids = [p.product_id for p in catalog]
    assert len(ids) == len(set(ids))


def test_values_are_sane(catalog):
    for p in catalog:
        assert p.price_krw > 0, p.product_id
        assert 0 <= p.kcal <= 1500, p.product_id
        assert p.sodium_mg <= 5000, p.product_id
        # macros should roughly explain calories (4/4/9 rule, loose tolerance)
        est = 4 * p.protein_g + 4 * p.carbs_g + 9 * p.fat_g
        assert abs(est - p.kcal) <= max(80, 0.35 * p.kcal), f"{p.product_id}: kcal {p.kcal} vs macros {est}"


def test_each_store_has_products(catalog):
    assert {p.store.value for p in catalog} == {"CU", "GS25", "Emart24"}


def test_prepared_items_have_instructions(catalog):
    for p in catalog:
        if "microwave" in [e.value for e in p.requires] or "kettle" in [e.value for e in p.requires]:
            assert p.prep_instructions, p.product_id


def test_sqlite_roundtrip(catalog):
    conn = init_db(":memory:")
    assert import_catalog(conn, CSV) == len(catalog)
    assert fetch_catalog(conn) == sorted(catalog, key=lambda p: p.product_id)


def test_source_column_is_loaded(catalog):
    assert all(p.source for p in catalog)


def test_validation_report_on_starter_catalog(catalog):
    from dormmeal.validation import catalog_report
    r = catalog_report(catalog)
    assert r["total"] == len(catalog)
    assert r["verified"] == 0 and r["verified_pct"] == 0
    assert r["issues"] == []


def test_validation_report_detects_problems(catalog):
    from dormmeal.validation import catalog_report
    bad = catalog[0].model_copy(update={"kcal": 900, "verified": True, "source": ""})
    dup = catalog[1].model_copy()
    r = catalog_report([bad, dup, dup])
    text = " ".join(r["issues"])
    assert "duplicated id" in text and "does not match macros" in text and "no source" in text


# ---- sourced catalog imported from the research workbook ----
SOURCED = Path(__file__).resolve().parent.parent / "data" / "catalog_sourced.csv"
FULL = Path(__file__).resolve().parent.parent / "data" / "catalog.csv"


def test_sourced_catalog_is_traceable_and_clean():
    from dormmeal.validation import catalog_report
    rows = load_catalog_csv(SOURCED)
    assert len(rows) >= 90
    assert all(p.verified and "http" in p.source and p.name_ko for p in rows)
    assert all(not p.allergens_known and not p.diet_tags for p in rows)   # unknown, never guessed
    assert catalog_report(rows)["issues"] == []


def test_full_catalog_combines_sourced_and_estimates():
    rows = load_catalog_csv(FULL)
    ids = [p.product_id for p in rows]
    assert len(ids) == len(set(ids))
    assert {p.store.value for p in rows} == {"CU", "GS25", "Emart24", "7-Eleven"}
    assert any(p.verified for p in rows) and any(not p.verified for p in rows)


def test_unknown_allergens_are_excluded_for_allergic_users():
    from dormmeal.tools import search_catalog
    rows = load_catalog_csv(FULL)
    allergic = search_catalog(rows, equipment=["microwave", "kettle", "fridge"], allergies=["milk"])
    # All products returned for allergic users must have known or inferred allergens
    assert all(p.allergens_known for p in allergic)
    # Inferred allergens (from LLM) count as known — full catalog has no remaining unknowns
    assert all(p.allergens_known for p in rows)


def test_sourced_only_filter():
    from dormmeal.models import Constraints
    from dormmeal.tools import search_for_constraints
    rows = load_catalog_csv(FULL)
    c = Constraints(weekly_budget_krw=80000, equipment=["microwave", "kettle", "fridge"], sourced_only=True)
    assert all(p.verified for p in search_for_constraints(rows, c))


def test_full_catalog_sqlite_roundtrip():
    rows = load_catalog_csv(FULL)
    conn = init_db(":memory:")
    assert import_catalog(conn, FULL) == len(rows)
    assert fetch_catalog(conn) == sorted(rows, key=lambda p: p.product_id)
