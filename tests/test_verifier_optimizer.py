from pathlib import Path

import pytest

from dormmeal.models import Constraints, Equipment, Meal, MealPlan, MealSlot, PlanItem
from dormmeal.optimizer import optimize
from dormmeal.tools import load_catalog_csv
from dormmeal.verifier import verify

CSV = Path(__file__).resolve().parent.parent / "data" / "catalog_v1.csv"
CATALOG = load_catalog_csv(CSV)
BY_ID = {p.product_id: p for p in CATALOG}
ALL_EQ = list(Equipment)


def full_plan(items):
    """21 meals, each with the given items."""
    return MealPlan(meals=[Meal(day=d, slot=s, items=[PlanItem(product_id=p, quantity=q) for p, q in items])
                           for d in range(1, 8) for s in MealSlot])


def rules(res):
    return {v.rule for v in res.violations}


# ---------------- verifier ----------------
def test_verifier_unknown_product():
    res = verify(full_plan([("XX999", 1)]), CATALOG, Constraints(weekly_budget_krw=100000))
    assert not res.valid and rules(res) == {"unknown_product"}


def test_verifier_flags_allergen_equipment_diet_store_preference():
    c = Constraints(weekly_budget_krw=10**7, allergies=["egg"], equipment=[], diet="vegetarian",
                    stores=["GS25"], disliked_product_ids=["CU005"])
    res = verify(full_plan([("CU005", 1)]), CATALOG, c)   # chicken bento, CU, needs microwave, has egg
    assert {"allergen", "equipment", "diet", "store", "preference"} <= rules(res)


def test_verifier_budget_and_variety():
    c = Constraints(weekly_budget_krw=1000, equipment=ALL_EQ)
    res = verify(full_plan([("CU012", 1)]), CATALOG, c)
    assert {"budget", "variety"} <= rules(res)


def test_verifier_structure_missing_and_extra_meal():
    c = Constraints(weekly_budget_krw=10**7, equipment=ALL_EQ, meals_per_day=2)
    plan = full_plan([("CU012", 1)])                      # breakfast should not be planned
    plan.meals = [m for m in plan.meals if not (m.day == 3 and m.slot == MealSlot.LUNCH)]
    details = " ".join(v.detail for v in verify(plan, CATALOG, c).violations if v.rule == "structure")
    assert "day 3 lunch is missing" in details and "breakfast should not be planned" in details


def test_verifier_skipped_meal_is_not_required():
    c = Constraints(weekly_budget_krw=10**7, equipment=ALL_EQ, skipped_meals=[(2, "dinner")])
    plan = full_plan([("CU012", 1)])
    plan.meals = [m for m in plan.meals if not (m.day == 2 and m.slot == MealSlot.DINNER)]
    assert "structure" not in rules(verify(plan, CATALOG, c))


def test_verifier_nutrition_low_kcal():
    res = verify(full_plan([("CU012", 1)]), CATALOG, Constraints(weekly_budget_krw=10**7, equipment=ALL_EQ,
                                                                  max_repeats_per_product=21))
    assert rules(res) == {"nutrition"}


# ---------------- optimizer ----------------
@pytest.fixture(scope="module")
def solved():
    c = Constraints(weekly_budget_krw=80000, equipment=["microwave", "fridge"], allergies=["nuts"])
    return c, optimize(CATALOG, c, time_limit_s=20)


def test_optimizer_returns_a_valid_plan(solved):
    c, r = solved
    assert r.plan is not None
    res = verify(r.plan, CATALOG, c)
    assert res.valid, [v.detail for v in res.violations]


def test_optimizer_hard_constraints(solved):
    c, r = solved
    used = {i.product_id for m in r.plan.meals for i in m.items}
    for pid in used:
        p = BY_ID[pid]
        assert "nuts" not in p.allergens and set(p.requires) <= set(c.equipment)


def test_optimizer_keeps_locked_meals_and_respects_skips():
    c = Constraints(weekly_budget_krw=70000, equipment=["microwave", "fridge"], skipped_meals=[(4, "lunch")])
    locked = [Meal(day=1, slot=MealSlot.BREAKFAST, items=[PlanItem(product_id="CU012", quantity=2)], locked=True)]
    r = optimize(CATALOG, c, locked=locked, time_limit_s=5)
    first = next(m for m in r.plan.meals if m.day == 1 and m.slot == MealSlot.BREAKFAST)
    assert first.items == locked[0].items
    assert not any(m.day == 4 and m.slot == MealSlot.LUNCH for m in r.plan.meals)
    assert "structure" not in rules(verify(r.plan, CATALOG, c))


def test_optimizer_reports_infeasible_budget():
    r = optimize(CATALOG, Constraints(weekly_budget_krw=5000, equipment=ALL_EQ), time_limit_s=3)
    assert r.status == "infeasible" and r.plan is None and "budget" in r.message


def test_optimizer_no_candidates():
    c = Constraints(weekly_budget_krw=70000, equipment=[], diet="halal_friendly")
    r = optimize(CATALOG, c, time_limit_s=1)
    assert r.status == "infeasible" and "No product" in r.message


def test_optimizer_explains_too_few_main_dishes():
    c = Constraints(weekly_budget_krw=75000, equipment=["microwave", "fridge"], allergies=["wheat"], stores=["GS25"])
    r = optimize(CATALOG, c, time_limit_s=1)
    assert r.status == "infeasible" and "main dishes" in r.message
