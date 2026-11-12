# DormMeal development log (weeks 1-2)

Written to be reused in the final report. Dates: 2026-11-02. Author: Rosano Thierry.

## 1. Scope of weeks 1-2
Plan: scope, schemas, repository and CI (week 1); catalog and deterministic core tools with unit tests (week 2).
Not in scope yet: Verifier, CP-SAT optimizer, LangGraph agent, Streamlit UI (weeks 3+).

## 2. What was built
| Component | File | Purpose |
|---|---|---|
| Data schemas | `dormmeal/models.py` | Typed contracts shared by catalog, tools, verifier and agent (Pydantic) |
| Database | `dormmeal/db.py` | SQLite schema: products, users, plans, preferences, event logs; CSV import; fetch |
| Catalog | `data/catalog_v1.csv` | 50 starter products, 3 chains, ~19 columns |
| Tools | `dormmeal/tools.py` | `load_catalog_csv`, `search_catalog`, `compute_totals`, promo functions |
| Data quality | `dormmeal/validation.py`, `scripts/validate_catalog.py` | Progress and anomaly report |
| Tests | `tests/` | 31 tests (unit, SQLite round-trip, Hypothesis property test) |
| CI | `.github/workflows/ci.yml` | Runs the tests on every push |

## 3. Design decisions and rationale
1. **Deterministic tools, no LLM for numbers.** Cost and nutrition are computed in code (`compute_totals`) so the final answer never depends on model arithmetic. This is the core claim of the project.
2. **Hard constraints enforced at search time.** `search_catalog` removes products with a declared allergen, missing equipment, wrong diet tag or a disliked id, so downstream components cannot select them by mistake. A Hypothesis property test checks this for 100 random constraint combinations.
3. **Equipment model.** A product lists the equipment it needs (`requires`); it is eligible only if that set is a subset of the user's equipment. `fridge` also covers chilled storage.
4. **Promo semantics.** `quantity` = units taken home. 1+1: paid = ceil(q/2). 2+1: paid = q - floor(q/3). Promos apply to the total weekly quantity of a product (one shopping trip), and nutrition counts all units taken, free ones included.
5. **Pydantic for every boundary** (CSV rows, DB rows, future LLM output) so invalid data fails early.
6. **Traceability.** `verified` and `source` columns separate real label data from estimates; the validation script reports the verified ratio.
7. **SQLite + CSV.** The CSV is the human-editable source of truth; SQLite is rebuilt from it with `scripts/load_catalog.py`.
8. **Allergen matching** is on lower-cased strings; the allergen vocabulary must stay consistent in the CSV.

## 4. Verification evidence
- `pytest -q`: 31 passed (version 0.2.0). Version 0.1.0: 28 passed.
- Covered: promo arithmetic (parametrized), equipment/allergen/diet/store/price/promo filters, promo applied across days, nutrition counting free units, unknown product error, CSV sanity (unique ids, kcal vs macros 4/4/9 within tolerance, sodium and price ranges), SQLite round-trip, validation report on good and bad catalogs.
- Property test: for random allergen, equipment and diet inputs, no returned product contains a banned allergen, needs missing equipment or violates the diet tag.

## 5. Facts checked from public sources (2026-11-02)
- **Promo meaning.** 1+1 means buy one and get one free; 2+1 means buy two and get one free, in convenience stores and supermarkets. Sources: https://gogohanguk.com/en/blog/tips-for-saving-money-in-korea/ and https://hangulheartbeat.blogspot.com/2026/03/k-culture-what-does-11-mean.html
- **Promos are common and shifting.** At CU, the sales share of 1+1 products rose from 17.2% (2020) to 29% (Jan-Feb 2023) while 2+1 fell from 67.1% to 61.4% of promo-product sales. Source: https://cm.asiae.co.kr/en/article/2023051215525359299
- **Other promo shapes exist** (e.g. a CU ramen 1+2 offer), which this model does not cover. Source: https://www.asiae.co.kr/en/article/2023062807514108401
- **Instant rice promos.** Emart24 ran 1+1 and 2+1 on all instant rice products (excluding bundles) in Sept 2025, which supports modelling promos on instant rice. Source: https://cm.asiae.co.kr/en/article/2025091609154278827
- **Sodium problem (motivation).** A Korea Consumer Agency test of 12 convenience-store kimbap rolls found 760 to 1,393 mg sodium per roll, i.e. 38-70% of the 2,000 mg daily reference. Source: http://www.newstomato.com/ReadNews.aspx?no=1316814
- **Why estimates must be replaced.** A third-party calorie site lists a CU tuna-mayo triangle kimbap at about 189 kcal for 105 g, while the starter estimate in this repo is 230 kcal. Third-party sites are not authoritative, but the gap shows the starter values are unreliable. Source: https://geniet.co.kr/review/42879

## 6. Limitations (state them in the report)
- All 150 catalog rows are estimates (50 starter rows + 100 added on 2026-11-12) (`verified = false`). No public price/nutrition API exists for the chains, and web sources found were scattered and user-generated, so verified data requires manual collection from labels and shelf tags.
- Prices and promos vary by store and month; the catalog is a dated snapshot.
- Only 1+1 and 2+1 promos are modelled; bundle deals, discounts and 1+2 are not.
- `vegetarian` tags are conservative; no `halal_friendly` tag is assigned because certification cannot be verified.
- No nutrition-target checking yet (that is the Verifier, week 3).

## 7. Remaining work
1. Collect real data: reach ~150 products and a high verified share (see `docs/DATA_COLLECTION_GUIDE.md`).
2. Push the repository to GitHub so CI runs (commands in README).
3. Week 3: Verifier (budget, allergens, equipment, diet, nutrition, variety) and CP-SAT optimizer.
4. Weeks 4-8: LangGraph agent, Streamlit UI, replanning, benchmark vs LLM-only, deployment.

## 8. Reproduce
```bash
pip install -r requirements-dev.txt
pytest -q
python scripts/validate_catalog.py
python scripts/load_catalog.py
```
