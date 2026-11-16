# Benchmark results

12 seeded scenarios (seed 42), optimizer time limit 15.0 s, catalog.csv.
Both planners are scored by the same Verifier. *Valid* = no violation at all; *hard constraints OK* = no allergen, equipment, diet, store, budget, variety, structure or unknown-product violation (nutrition gaps allowed).

| Planner | Valid | Hard constraints OK | Plan parsed | Avg time (s) | Violations (count) |
|---|---|---|---|---|---|
| DormMeal | 8.3% | 66.7% | 66.7% | 17.7 | {'nutrition': 63, 'no_plan': 4} |
| LLM-only | not run (no GEMINI_API_KEY) | | | | |
