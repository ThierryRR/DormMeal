# Evaluation (weeks 7 and 11)

All numbers below come from scripts in `benchmark/` run on 2026-11-12 with the **estimated** catalog
(150 products, 0% verified). They show how the system behaves; they are not facts about real prices.

## 1. Benchmark: DormMeal vs LLM-only (`benchmark/RESULTS.md`)
12 seeded scenarios (random budget 45k-90k KRW, 2-3 meals/day, equipment, allergies, diet, stores).
Every plan is scored by the same Verifier.

| Planner | Valid | Hard constraints OK | Notes |
|---|---|---|---|
| DormMeal | 8.3% (1/12) | 10/10 plans returned | 2 scenarios correctly refused with an explanation (too few main dishes) |
| LLM-only | not run yet | | needs `GEMINI_API_KEY`: `python benchmark/run_benchmark.py` |

Reading: DormMeal never breaks a hard constraint (allergen, equipment, diet, store, budget, variety).
Most scenarios fail only on **nutrition**, because their budgets (45k-65k) are below what the estimated
catalog needs (section 2). The LLM-only column is the main missing result before the final report.

## 2. Budget sensitivity (`benchmark/SENSITIVITY.md`)
Days (out of 7) that miss a nutrition target, 3 meals/day:

| Profile | 50k | 60k | 70k | 80k | 90k | 100k |
|---|---|---|---|---|---|---|
| no equipment | 7 | 7 | 7 | 6 | 5 | 2 |
| microwave | 6 | 5 | 3 | 0 | 0 | 0 |
| microwave + fridge | 6 | 7 | 2 | 0 | 1 | 0 |
| microwave + fridge, vegetarian | 7 | 6 | 2 | 0 | 0 | 0 |

Findings:
- With a microwave, about **80,000 KRW/week (~11,400 KRW/day)** is enough for all targets (estimated prices).
- Without any equipment, even 100,000 KRW is not enough on some days: the ready-to-eat products are
  low in protein per won. Access to a microwave matters more than a vegetarian diet.
- Non-monotonic cells (e.g. 90k with fridge) come from the 8 s time limit: the search is not always optimal.
- Allergies matter a lot: with a wheat allergy only a few main dishes remain (most kimbap and noodles
  contain wheat), and DormMeal refuses to plan instead of returning an unsafe plan.

## 3. Tests (`pytest -q`)
74 tests: unit tests, SQLite round trips, Streamlit smoke test, and two property tests
(search never returns an unsafe product; the optimizer never returns a plan with a hard violation).

## 4. Limits of this evaluation
- Catalog values are estimates: absolute budgets will change once real labels are collected.
- No real users yet: usefulness, trust and readability of the plans are not measured.
- The simulated focus group (week 10 notebook) only produces hypotheses to test with real students.
