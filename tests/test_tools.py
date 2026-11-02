from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from dormmeal.models import (Diet, Equipment, Meal, MealPlan, MealSlot, PlanItem,
                             PromoType, Store)
from dormmeal.tools import (compute_totals, line_cost, load_catalog_csv, paid_units,
                            search_catalog)

CSV = Path(__file__).resolve().parent.parent / "data" / "catalog_v1.csv"
CATALOG = load_catalog_csv(CSV)
BY_ID = {p.product_id: p for p in CATALOG}
ALLERGENS = sorted({a for p in CATALOG for a in p.allergens})


# ---- promos ----
@pytest.mark.parametrize("q,expected", [(1, 1), (2, 1), (3, 2), (4, 2), (5, 3)])
def test_one_plus_one(q, expected):
    assert paid_units(q, PromoType.ONE_PLUS_ONE) == expected


@pytest.mark.parametrize("q,expected", [(1, 1), (2, 2), (3, 2), (4, 3), (6, 4)])
def test_two_plus_one(q, expected):
    assert paid_units(q, PromoType.TWO_PLUS_ONE) == expected


def test_line_cost_with_promo():
    p = BY_ID["CU002"]  # 1+1, 1500 KRW
    assert line_cost(p, 2) == 1500
    assert line_cost(p, 3) == 3000


# ---- search ----
def test_search_respects_equipment():
    res = search_catalog(CATALOG, equipment=[])
    for p in res:
        assert not p.requires


def test_search_microwave_unlocks_bentos():
    without = {p.product_id for p in search_catalog(CATALOG, equipment=[])}
    with_mw = {p.product_id for p in search_catalog(CATALOG, equipment=[Equipment.MICROWAVE])}
    assert "CU005" not in without and "CU005" in with_mw


def test_search_excludes_allergen():
    res = search_catalog(CATALOG, equipment=list(Equipment), allergies=["Egg"])
    assert res and all("egg" not in p.allergens for p in res)


def test_search_vegetarian():
    res = search_catalog(CATALOG, equipment=list(Equipment), diet=Diet.VEGETARIAN)
    assert res and all(Diet.VEGETARIAN in p.diet_tags for p in res)


def test_search_store_price_and_exclusions():
    res = search_catalog(CATALOG, stores=[Store.CU], equipment=list(Equipment), max_price_krw=1500,
                         exclude_ids=["CU001"])
    assert all(p.store == Store.CU and p.price_krw <= 1500 and p.product_id != "CU001" for p in res)


def test_search_promo_only():
    res = search_catalog(CATALOG, equipment=list(Equipment), promo_only=True)
    assert res and all(p.promo_type != PromoType.NONE for p in res)


@settings(max_examples=100, deadline=None)
@given(allergies=st.lists(st.sampled_from(ALLERGENS), max_size=4),
       equipment=st.lists(st.sampled_from(list(Equipment)), unique=True, max_size=3),
       diet=st.sampled_from(list(Diet)))
def test_property_search_never_returns_unsafe_product(allergies, equipment, diet):
    for p in search_catalog(CATALOG, equipment=equipment, allergies=allergies, diet=diet):
        assert not (set(allergies) & set(p.allergens))
        assert set(p.requires) <= set(equipment)
        assert diet == Diet.NONE or diet in p.diet_tags


# ---- totals ----
def _plan(*meals):
    return MealPlan(meals=[Meal(day=d, slot=MealSlot.LUNCH, items=[PlanItem(product_id=i, quantity=q) for i, q in items])
                           for d, items in meals])


def test_totals_simple():
    plan = _plan((1, [("CU001", 1), ("CU012", 2)]))
    t = compute_totals(plan, CATALOG)
    assert t.total_cost_krw == 1400 + 2 * 1000
    assert t.daily_kcal[1] == pytest.approx(230 + 2 * 90)
    assert t.daily_protein_g[1] == pytest.approx(6 + 2 * 1)


def test_totals_promo_applies_across_the_week():
    # CU002 is 1+1 at 1500: 1 unit on day 1 and 1 on day 2 -> total 2 units -> pay once
    plan = _plan((1, [("CU002", 1)]), (2, [("CU002", 1)]))
    t = compute_totals(plan, CATALOG)
    assert t.total_cost_krw == 1500
    assert t.units_per_product["CU002"] == 2


def test_totals_nutrition_counts_all_units_taken():
    plan = _plan((1, [("CU002", 2)]))
    t = compute_totals(plan, CATALOG)
    assert t.daily_kcal[1] == pytest.approx(480)
    assert t.total_cost_krw == 1500


def test_totals_unknown_product():
    with pytest.raises(ValueError):
        compute_totals(_plan((1, [("NOPE", 1)])), CATALOG)
