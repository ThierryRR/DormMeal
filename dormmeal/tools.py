"""Deterministic tools used by the agent: catalog loading, search and cost/nutrition totals.

Promo rules (quantity = units taken home):
  1+1 : buy one, get one free  -> paid units = ceil(q / 2)
  2+1 : buy two, get one free  -> paid units = q - q // 3
Promos are applied to the total quantity of a product over the whole week
(one shopping trip), not per meal.
"""
import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional

from .models import (Constraints, Diet, Equipment, MealPlan, Product, PromoType,
                     Store, Totals)

LIST_SEP = ";"


def _split(value: str) -> list[str]:
    return [v.strip() for v in value.split(LIST_SEP) if v.strip()]


def load_catalog_csv(path: str | Path) -> list[Product]:
    products = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            products.append(Product(
                product_id=row["product_id"],
                name_en=row["name_en"],
                store=row["store"],
                category=row["category"],
                price_krw=int(row["price_krw"]),
                promo_type=row["promo_type"] or "none",
                kcal=float(row["kcal"]),
                protein_g=float(row["protein_g"]),
                carbs_g=float(row["carbs_g"]),
                fat_g=float(row["fat_g"]),
                sodium_mg=float(row["sodium_mg"]),
                allergens=[a.lower() for a in _split(row["allergens"])],
                diet_tags=_split(row["diet_tags"]),
                requires=_split(row["requires"]),
                prep_instructions=row["prep_instructions"] or None,
                description=row["description"],
                last_updated=row["last_updated"],
                verified=row["verified"].strip().lower() == "true",
            ))
    return products


def paid_units(quantity: int, promo: PromoType) -> int:
    if promo == PromoType.ONE_PLUS_ONE:
        return math.ceil(quantity / 2)
    if promo == PromoType.TWO_PLUS_ONE:
        return quantity - quantity // 3
    return quantity


def line_cost(product: Product, quantity: int) -> int:
    return product.price_krw * paid_units(quantity, product.promo_type)


def search_catalog(
    catalog: Iterable[Product],
    stores: Optional[list[Store]] = None,
    equipment: Optional[list[Equipment]] = None,
    allergies: Optional[list[str]] = None,
    diet: Diet = Diet.NONE,
    max_price_krw: Optional[int] = None,
    category: Optional[str] = None,
    exclude_ids: Optional[list[str]] = None,
    promo_only: bool = False,
) -> list[Product]:
    """Return products compatible with the user's hard constraints (never an unsafe one)."""
    available = set(equipment or [])
    banned = {a.lower() for a in (allergies or [])}
    excluded = set(exclude_ids or [])
    result = []
    for p in catalog:
        if stores is not None and p.store not in stores:
            continue
        if not set(p.requires) <= available:
            continue
        if banned & set(p.allergens):
            continue
        if diet != Diet.NONE and diet not in p.diet_tags:
            continue
        if max_price_krw is not None and p.price_krw > max_price_krw:
            continue
        if category is not None and p.category != category:
            continue
        if p.product_id in excluded:
            continue
        if promo_only and p.promo_type == PromoType.NONE:
            continue
        result.append(p)
    return result


def search_for_constraints(catalog: Iterable[Product], c: Constraints) -> list[Product]:
    return search_catalog(catalog, stores=c.stores, equipment=c.equipment, allergies=c.allergies,
                          diet=c.diet, exclude_ids=c.disliked_product_ids)


def compute_totals(plan: MealPlan, catalog: Iterable[Product]) -> Totals:
    """Cost (with promos over the whole week) and daily nutrition. Pure code, no LLM."""
    by_id = {p.product_id: p for p in catalog}
    units: dict[str, int] = defaultdict(int)
    kcal: dict[int, float] = defaultdict(float)
    protein: dict[int, float] = defaultdict(float)
    sodium: dict[int, float] = defaultdict(float)

    unknown = {i.product_id for m in plan.meals for i in m.items if i.product_id not in by_id}
    if unknown:
        raise ValueError(f"Unknown product ids: {sorted(unknown)}")

    for meal in plan.meals:
        for item in meal.items:
            p = by_id[item.product_id]
            units[p.product_id] += item.quantity
            kcal[meal.day] += p.kcal * item.quantity
            protein[meal.day] += p.protein_g * item.quantity
            sodium[meal.day] += p.sodium_mg * item.quantity

    total = sum(line_cost(by_id[pid], q) for pid, q in units.items())
    return Totals(total_cost_krw=total, daily_kcal=dict(kcal), daily_protein_g=dict(protein),
                  daily_sodium_mg=dict(sodium), units_per_product=dict(units))
