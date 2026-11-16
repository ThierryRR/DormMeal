# Benchmark results

12 seeded scenarios (seed 42), optimizer time limit 15.0 s, catalog.csv.
Both planners are scored by the same Verifier. *Valid* = no violation at all; *hard constraints OK* = no allergen, equipment, diet, store, budget, variety, structure or unknown-product violation (nutrition gaps allowed).

| Planner | Valid | Hard constraints OK | Plan parsed | Avg time (s) | Violations (count) |
|---|---|---|---|---|---|
| DormMeal | 16.7% | 66.7% | 66.7% | 17.8 | {'nutrition': 59, 'no_plan': 4} |
| LLM-only | 0.0% | 0.0% | 100.0% | 3.1 | {'equipment': 62, 'variety': 13, 'budget': 10, 'nutrition': 133, 'store': 5, 'allergen': 7} |
