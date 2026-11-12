# Benchmark results

12 seeded scenarios (seed 42), optimizer time limit 10.0 s, catalog of 150 estimated products.
Both planners are scored by the same Verifier. *Valid* = no violation at all; *hard constraints OK* = no allergen, equipment, diet, store, budget, variety, structure or unknown-product violation (nutrition gaps allowed).

| Planner | Valid | Hard constraints OK | Plan parsed | Avg time (s) | Violations (count) |
|---|---|---|---|---|---|
| DormMeal | 8.3% | 83.3% | 83.3% | 8.4 | {'nutrition': 86, 'no_plan': 2} |
| LLM-only | not run (no GEMINI_API_KEY) | | | | |
