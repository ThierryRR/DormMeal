"""Verifier: checks a meal plan against the user's constraints. Pure code, no LLM.

Every plan shown to the user (from the optimizer or from an LLM-only baseline) goes through `verify`.

Nutrition targets are daily targets for 3 meals. When the user plans fewer meals per day, or skips
meals, the targets of that day are scaled by (meals eaten that day / 3), assuming the other meals
come from elsewhere (cafeteria, restaurant).
"""
from collections import Counter
from typing import Iterable

from .models import (Constraints, Diet, MealPlan, Product, VerificationResult, Violation,
                     active_slots)
from .tools import compute_totals

# Tolerance so that rounding in the optimizer (integer kcal, 0.1 g protein) does not create violations
_EPS = 1e-6


def expected_meals(c: Constraints) -> set[tuple[int, str]]:
    skipped = {(d, s.value if hasattr(s, "value") else s) for d, s in c.skipped_meals}
    return {(d, s.value) for d in range(1, 8) for s in active_slots(c.meals_per_day)} - skipped


def day_factor(c: Constraints, day: int) -> float:
    eaten = sum(1 for d, _ in expected_meals(c) if d == day)
    return eaten / 3


def verify(plan: MealPlan, catalog: Iterable[Product], c: Constraints) -> VerificationResult:
    catalog = list(catalog)
    by_id = {p.product_id: p for p in catalog}
    v: list[Violation] = []

    unknown = sorted({i.product_id for m in plan.meals for i in m.items if i.product_id not in by_id})
    for pid in unknown:
        v.append(Violation(rule="unknown_product", detail=f"{pid} is not in the catalog"))
    if unknown:
        return VerificationResult(valid=False, violations=v)

    # structure: every expected meal present exactly once, no meal in a skipped/inactive slot
    keys = [(m.day, m.slot.value) for m in plan.meals]
    exp = expected_meals(c)
    for k, n in Counter(keys).items():
        if n > 1:
            v.append(Violation(rule="structure", detail=f"day {k[0]} {k[1]} appears {n} times"))
    for k in sorted(exp - set(keys)):
        v.append(Violation(rule="structure", detail=f"day {k[0]} {k[1]} is missing"))
    for m in plan.meals:
        if (m.day, m.slot.value) not in exp and m.items:
            v.append(Violation(rule="structure", detail=f"day {m.day} {m.slot.value} should not be planned"))
        elif (m.day, m.slot.value) in exp and not m.items:
            v.append(Violation(rule="structure", detail=f"day {m.day} {m.slot.value} is empty"))

    # per-product hard constraints
    banned = {a.lower() for a in c.allergies}
    equipment = set(c.equipment)
    # locked meals were already eaten (replanning): they are not re-checked for products
    used = {i.product_id for m in plan.meals if not m.locked for i in m.items}
    for pid in sorted(used):
        p = by_id[pid]
        if banned & set(p.allergens):
            v.append(Violation(rule="allergen", detail=f"{pid} {p.name_en} contains {sorted(banned & set(p.allergens))}"))
        elif banned and not p.allergens_known:
            v.append(Violation(rule="allergen", detail=f"{pid} {p.name_en} has no allergen information"))
        missing = set(p.requires) - equipment
        if missing:
            v.append(Violation(rule="equipment", detail=f"{pid} {p.name_en} needs {sorted(e.value for e in missing)}"))
        if c.diet != Diet.NONE and c.diet not in p.diet_tags:
            v.append(Violation(rule="diet", detail=f"{pid} {p.name_en} is not tagged {c.diet.value}"))
        if p.store not in c.stores:
            v.append(Violation(rule="store", detail=f"{pid} is sold at {p.store.value}, not a selected store"))
        if pid in c.disliked_product_ids:
            v.append(Violation(rule="preference", detail=f"{pid} {p.name_en} was rejected by the user"))

    # variety: number of meals in which a product appears
    meals_per_product = Counter(i.product_id for m in plan.meals for i in {x.product_id: x for x in m.items}.values())
    for pid, n in meals_per_product.items():
        if n > c.max_repeats_per_product:
            v.append(Violation(rule="variety",
                               detail=f"{pid} appears in {n} meals (max {c.max_repeats_per_product})"))

    totals = compute_totals(plan, catalog)
    if totals.total_cost_krw > c.weekly_budget_krw:
        v.append(Violation(rule="budget",
                           detail=f"total {totals.total_cost_krw} KRW > budget {c.weekly_budget_krw} KRW"))

    t = c.targets
    for day in range(1, 8):
        f = day_factor(c, day)
        if f == 0:
            continue
        kcal = totals.daily_kcal.get(day, 0)
        lo, hi = t.kcal_per_day[0] * f, t.kcal_per_day[1] * f
        if kcal < lo - _EPS or kcal > hi + _EPS:
            v.append(Violation(rule="nutrition", detail=f"day {day}: {kcal:.0f} kcal outside {lo:.0f}-{hi:.0f}"))
        prot = totals.daily_protein_g.get(day, 0)
        if prot < t.protein_g_per_day_min * f - _EPS:
            v.append(Violation(rule="nutrition",
                               detail=f"day {day}: protein {prot:.1f} g < {t.protein_g_per_day_min * f:.0f} g"))
        sod = totals.daily_sodium_mg.get(day, 0)
        if sod > t.sodium_mg_per_day_max * f + _EPS:
            v.append(Violation(rule="nutrition",
                               detail=f"day {day}: sodium {sod:.0f} mg > {t.sodium_mg_per_day_max * f:.0f} mg"))

    return VerificationResult(valid=not v, totals=totals, violations=v)
