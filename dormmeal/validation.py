"""Catalog quality report: used to track data collection progress and to catch input mistakes."""
from collections import Counter
from typing import Iterable

from .models import Product

TARGET_PRODUCTS = 150


def catalog_report(products: Iterable[Product]) -> dict:
    products = list(products)
    ids = [p.product_id for p in products]
    verified = [p for p in products if p.verified]
    issues: list[str] = []

    for pid, n in Counter(ids).items():
        if n > 1:
            issues.append(f"{pid}: duplicated id")
    for p in products:
        est = 4 * p.protein_g + 4 * p.carbs_g + 9 * p.fat_g
        if abs(est - p.kcal) > max(80, 0.35 * p.kcal):
            issues.append(f"{p.product_id}: kcal {p.kcal:.0f} does not match macros (~{est:.0f})")
        if p.sodium_mg > 3000:
            issues.append(f"{p.product_id}: sodium {p.sodium_mg:.0f} mg looks too high")
        if p.price_krw < 300 or p.price_krw > 20000:
            issues.append(f"{p.product_id}: price {p.price_krw} KRW looks unusual")
        if p.requires and any(e.value in ("microwave", "kettle") for e in p.requires) and not p.prep_instructions:
            issues.append(f"{p.product_id}: needs equipment but has no prep_instructions")
        if p.verified and not p.source:
            issues.append(f"{p.product_id}: verified=true but no source")

    return {
        "total": len(products),
        "target": TARGET_PRODUCTS,
        "progress_pct": round(100 * len(products) / TARGET_PRODUCTS, 1),
        "verified": len(verified),
        "verified_pct": round(100 * len(verified) / len(products), 1) if products else 0.0,
        "per_store": dict(Counter(p.store.value for p in products)),
        "per_category": dict(Counter(p.category for p in products)),
        "with_promo": sum(1 for p in products if p.promo_type.value != "none"),
        "issues": issues,
    }
