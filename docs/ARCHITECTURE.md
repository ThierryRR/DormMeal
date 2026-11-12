# Architecture

## Design principle
A predictable workflow with one gate (the Verifier), not a free-form agent loop. The LLM is confined to
turning free text into validated structured data. Everything numeric (cost, promos, nutrition) and every
decision about which products are safe is done by code. This follows the "simplest adequate design" rule:
the task (plan within constraints) is well scoped, so an optimizer is more reliable than an LLM.

## Components
| Module | Responsibility | LLM? |
|---|---|---|
| `parser.py` | Free text -> `Constraints`. Gemini JSON validated by Pydantic; unknown allergens dropped; rule fallback | optional |
| `tools.py` | `search_catalog` (hard filters), `compute_totals` (promos over the week, nutrition of all units) | no |
| `optimizer.py` | CP-SAT model: x[meal, product] units (0-2), y[meal, product] used. Hard: candidates only, budget, 1-3 products and 250-1,000 kcal per meal, at least one main product, max 3 meals per product, locked meals. Soft (weighted): daily kcal, protein, sodium. Warm start (greedy), budget lower bound, stability bonus when replanning | no |
| `verifier.py` | Re-checks every plan: unknown product, structure, allergen, equipment, diet, store, preference, variety, budget, nutrition | no |
| `events.py` | Free text -> `Event` (sold_out, skip_meal, budget_change, equipment_change); `apply_event` | optional |
| `agent.py` | parse -> search -> optimize -> verify -> explain; `replan`; shopping list; trace per node | no |
| `db.py` | SQLite tables products, users, plans, preferences, event_logs | no |
| `app.py` | Streamlit UI | no |

## Key decisions and why
1. **CP-SAT instead of an LLM planner.** Hard constraints (allergens, budget) must hold every time; the
   property test checks it on random inputs.
2. **Soft nutrition.** When the budget is too small, the user still gets the closest plan plus a clear list
   of the days that miss a target, instead of "no solution".
3. **Meal realism rules** (main product, kcal per meal) were added after the first plans contained meals
   such as "two plain rice cups".
4. **Explicit state machine instead of LangGraph** (planned in week 1): same nodes, no extra dependency,
   easier to test.
5. **Stability bonus when replanning**: a sold-out item should not reshuffle the whole week.
6. **Time limit (20 s)**: the plan is the best found, not always the proven optimum (see `docs/EVALUATION.md`).

## Data flow for replanning
`replan(state, text, today, next_meal)`: parse the event -> update constraints (e.g. add to
`unavailable_product_ids`) -> lock meals before (today, next_meal) -> optimize the rest with the old plan as
hint and stability bonus -> verify -> message "N meals kept, M upcoming meals changed".

## Security and privacy
- API key read from the environment or Streamlit secrets; never in code, logs or notebook outputs.
- LLM output is data: validated against a schema, unknown values dropped, rule fallback on failure.
- Stored data: nickname, constraints (including allergies), plans, likes. No real name, no location.
