# Evaluation (weeks 7 and 11)

All numbers below come from scripts in `benchmark/` run on 2026-11-12 with `data/catalog.csv`: 98 sourced
products (research workbook) + 150 estimated products. Results that mix both kinds of data show how the
system behaves; only the "sourced products only" row relies on sourced data alone.

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

## 2. Budget sensitivity (`benchmark/SENSITIVITY.md`, 15 s per plan)
Days (out of 7) that miss a nutrition target, 3 meals/day:

| Profile | 50k | 60k | 70k | 80k | 90k | 100k |
|---|---|---|---|---|---|---|
| no equipment | 7 | 7 | 7 | 3 | 0 | 1 |
| microwave | 7 | 5 | 3 | 0 | 0 | 0 |
| microwave + fridge | 7 | 6 | 2 | 0 | 0 | 0 |
| microwave + fridge, vegetarian | 6 | 6 | 2 | 0 | 0 | 0 |
| all equipment, sourced products only | 6 | 7 | 7 | 3 | 4 | 0 |

Findings:
- With a microwave, about **80,000 KRW/week (~11,400 KRW/day)** meets every daily target.
- Without equipment, about 90,000 KRW is needed: ready-to-eat products give less protein per won.
- With **sourced products only**, targets are met only at 100,000 KRW: the sourced data contain few meals and no
  plain protein foods (eggs, chicken breast, tofu). Collecting those is the most useful next data task.
- Non-monotonic cells (e.g. 100k without equipment, 90k sourced-only) come from the time limit: the search
  is not always optimal.
- Allergies matter a lot: sourced products have no allergen data and are excluded for allergic users; with a
  wheat allergy only a few main dishes remain, and DormMeal refuses to plan instead of returning an unsafe plan.

## 3. Tests (`pytest -q`)
79 tests: unit tests, SQLite round trips, Streamlit smoke test, and two property tests
(search never returns an unsafe product; the optimizer never returns a plan with a hard violation).

## 4. Limits of this evaluation
- 150 of 248 products are still estimates; sourced prices are catalog reference prices, not shelf prices.
- No real users yet: usefulness, trust and readability of the plans are not measured.
- The simulated focus group (week 10 notebook) only produces hypotheses to test with real students.
