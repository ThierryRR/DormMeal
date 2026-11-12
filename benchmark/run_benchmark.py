"""Benchmark: DormMeal (optimizer + Verifier) vs an LLM-only planner, on the same scenarios.

Both planners are scored by the same Verifier, so the comparison is about valid plans, not style.

Usage:
  python benchmark/run_benchmark.py                 # DormMeal + LLM-only (needs GEMINI_API_KEY)
  python benchmark/run_benchmark.py --skip-llm      # DormMeal only
  python benchmark/run_benchmark.py --n 12 --time-limit 10

Writes benchmark/results.json and benchmark/RESULTS.md.
"""
import argparse
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dormmeal import llm  # noqa: E402
from dormmeal.models import Constraints, MealPlan, active_slots  # noqa: E402
from dormmeal.optimizer import optimize  # noqa: E402
from dormmeal.tools import load_catalog_csv  # noqa: E402
from dormmeal.verifier import verify  # noqa: E402

CATALOG = load_catalog_csv(ROOT / "data" / "catalog.csv")
BY_ID = {p.product_id: p for p in CATALOG}
ALLERGENS = ["egg", "soy", "wheat", "milk", "fish", "pork", "beef", "chicken", "nuts"]
EQUIPMENT_SETS = [[], ["microwave"], ["kettle"], ["microwave", "fridge"], ["microwave", "kettle", "fridge"]]


def scenarios(n: int, seed: int = 42) -> list[Constraints]:
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        out.append(Constraints(
            weekly_budget_krw=rng.choice([45000, 55000, 65000, 75000, 90000]),
            meals_per_day=rng.choice([2, 3, 3]),
            equipment=rng.choice(EQUIPMENT_SETS),
            allergies=rng.sample(ALLERGENS, rng.choice([0, 0, 1, 2])),
            diet=rng.choice(["none", "none", "none", "vegetarian"]),
            stores=rng.choice([["CU", "GS25", "Emart24"], ["CU", "GS25", "Emart24"], ["GS25"], ["CU", "Emart24"]]),
        ))
    return out


def catalog_text() -> str:
    head = "id|name|store|category|price|promo|kcal|protein|sodium|allergens|diet|requires"
    rows = [f"{p.product_id}|{p.name_en}|{p.store.value}|{p.category}|{p.price_krw}|{p.promo_type.value}|"
            f"{p.kcal:.0f}|{p.protein_g:.0f}|{p.sodium_mg:.0f}|{';'.join(p.allergens)}|"
            f"{';'.join(d.value for d in p.diet_tags)}|{';'.join(e.value for e in p.requires)}" for p in CATALOG]
    return head + "\n" + "\n".join(rows)


LLM_PROMPT = """You are a meal planner. Build a 7-day plan using ONLY products from this catalog.
{catalog}

Rules:
- Weekly budget: {budget} KRW. Promotions apply to the weekly quantity of a product:
  1+1 -> pay ceil(q/2) units, 2+1 -> pay q - floor(q/3) units.
- Meals per day: {meals} (slots: {slots}); days 1-7. Each meal has 1-3 products.
- Never use a product containing these allergens: {allergies}.
- Only products whose 'requires' equipment is available: {equipment}.
- Diet: {diet} (if vegetarian, only products tagged vegetarian).
- Stores allowed: {stores}.
- A product may appear in at most {repeats} meals per week.
- Per day (for 3 meals; scale by meals/3): {kmin}-{kmax} kcal, at least {prot} g protein, at most {sod} mg sodium.
Return ONLY JSON: {{"meals": [{{"day": 1, "slot": "lunch", "items": [{{"product_id": "CU001", "quantity": 1}}]}}, ...]}}"""


def llm_plan(c: Constraints) -> MealPlan | None:
    t = c.targets
    prompt = LLM_PROMPT.format(catalog=catalog_text(), budget=c.weekly_budget_krw, meals=c.meals_per_day,
                               slots=", ".join(s.value for s in active_slots(c.meals_per_day)),
                               allergies=", ".join(c.allergies) or "none",
                               equipment=", ".join(e.value for e in c.equipment) or "none",
                               diet=c.diet.value, stores=", ".join(s.value for s in c.stores),
                               repeats=c.max_repeats_per_product, kmin=t.kcal_per_day[0], kmax=t.kcal_per_day[1],
                               prot=t.protein_g_per_day_min, sod=t.sodium_mg_per_day_max)
    try:
        data = llm.extract_json(llm.chat([{"role": "user", "content": prompt}], temperature=0))
        return MealPlan.model_validate(data) if data else None
    except Exception:
        return None


def score(plan, c):
    if plan is None:
        return {"valid": False, "parsed": False, "violations": {"no_plan": 1}, "cost": None, "hard_ok": False}
    res = verify(plan, CATALOG, c)
    rules = Counter(v.rule for v in res.violations)
    hard = {r: n for r, n in rules.items() if r != "nutrition"}
    return {"valid": res.valid, "parsed": True, "violations": dict(rules),
            "cost": res.totals.total_cost_krw if res.totals else None, "hard_ok": not hard}


def summarize(rows, key):
    rs = [r[key] for r in rows if key in r]
    n = len(rs)
    if not n:
        return None
    viol = Counter()
    for r in rs:
        viol.update(r["violations"])
    return {"n": n, "valid_pct": round(100 * sum(r["valid"] for r in rs) / n, 1),
            "hard_constraints_ok_pct": round(100 * sum(r["hard_ok"] for r in rs) / n, 1),
            "parsed_pct": round(100 * sum(r["parsed"] for r in rs) / n, 1),
            "avg_seconds": round(sum(r["seconds"] for r in rs) / n, 1),
            "violations_total": dict(viol)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--time-limit", type=float, default=10)
    ap.add_argument("--skip-llm", action="store_true")
    a = ap.parse_args()
    use_llm = not a.skip_llm and llm.available()
    rows = []
    for i, c in enumerate(scenarios(a.n)):
        row = {"scenario": i + 1, "constraints": json.loads(c.model_dump_json(include={
            "weekly_budget_krw", "meals_per_day", "equipment", "allergies", "diet", "stores"}))}
        t0 = time.time()
        r = optimize(CATALOG, c, time_limit_s=a.time_limit)
        row["dormmeal"] = {**score(r.plan, c), "seconds": round(time.time() - t0, 1), "status": r.status}
        if use_llm:
            t0 = time.time()
            row["llm_only"] = {**score(llm_plan(c), c), "seconds": round(time.time() - t0, 1)}
        rows.append(row)
        print(f"#{i+1:02d} budget={c.weekly_budget_krw} meals={c.meals_per_day} eq={[e.value for e in c.equipment]} "
              f"allerg={c.allergies} diet={c.diet.value} | DormMeal valid={row['dormmeal']['valid']} "
              f"hard_ok={row['dormmeal']['hard_ok']} {row['dormmeal']['violations']}"
              + (f" | LLM valid={row['llm_only']['valid']} hard_ok={row['llm_only']['hard_ok']}" if use_llm else ""))
    summary = {"dormmeal": summarize(rows, "dormmeal"), "llm_only": summarize(rows, "llm_only"),
               "llm_model": llm.MODEL if use_llm else None, "time_limit_s": a.time_limit,
               "catalog": "catalog.csv"}
    out = Path(__file__).resolve().parent
    (out / "results.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    md = ["# Benchmark results", "",
          f"{a.n} seeded scenarios (seed 42), optimizer time limit {a.time_limit} s, catalog.csv.",
          "Both planners are scored by the same Verifier. *Valid* = no violation at all; "
          "*hard constraints OK* = no allergen, equipment, diet, store, budget, variety, structure or unknown-product "
          "violation (nutrition gaps allowed).", "",
          "| Planner | Valid | Hard constraints OK | Plan parsed | Avg time (s) | Violations (count) |",
          "|---|---|---|---|---|---|"]
    for name, s in (("DormMeal", summary["dormmeal"]), ("LLM-only", summary["llm_only"])):
        if s:
            md.append(f"| {name} | {s['valid_pct']}% | {s['hard_constraints_ok_pct']}% | {s['parsed_pct']}% | "
                      f"{s['avg_seconds']} | {s['violations_total']} |")
        else:
            md.append(f"| {name} | not run (no GEMINI_API_KEY) | | | | |")
    (out / "RESULTS.md").write_text("\n".join(md) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
