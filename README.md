# DormMeal (weeks 1-2: data layer and tools)

Convenience-store meal planning agent for international students in Korean dorms.
This repo currently contains the foundations: schemas, SQLite database, starter catalog,
deterministic tools (`search_catalog`, `compute_totals`) and tests.

## Setup
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -q
python scripts/load_catalog.py        # creates dormmeal.db from data/catalog_v1.csv
```

## Structure
```
dormmeal/models.py   Pydantic schemas (Product, Constraints, MealPlan, Event, ...)
dormmeal/db.py       SQLite schema + catalog import
dormmeal/tools.py    load_catalog_csv, search_catalog, compute_totals (promo logic)
dormmeal/validation.py  catalog quality / progress report
data/catalog_v1.csv  150 products (50 per chain), estimates, verified=false
scripts/             load_catalog.py, validate_catalog.py
docs/                DEVELOPMENT_LOG.md (report notes), DATA_COLLECTION_GUIDE.md
tests/               unit + property tests (Hypothesis)
notebooks/           week-10 lab: RAG agent + simulated focus group
.github/workflows/   CI: runs pytest on every push
```

## IMPORTANT: catalog data
`data/catalog_v1.csv` (150 rows) is a **set of estimates** (generic product types, approximate
prices and nutrition). Every row has `verified = false`. Replace values by real ones
(store website, shelf label, nutrition label), set `verified = true`, and update `last_updated`.
Run `python scripts/validate_catalog.py` to see progress and the verified ratio (report it in your final report).
See `docs/DATA_COLLECTION_GUIDE.md`.

## Conventions
- `;` separates list values in CSV (allergens, diet_tags, requires).
- `requires`: equipment needed to prepare or store the product (microwave, kettle, fridge).
- Promos: 1+1 -> paid = ceil(q/2); 2+1 -> paid = q - q//3; applied to total weekly quantity.
- Nutrition always counts all units taken (including free units).

## Push to GitHub
```bash
# create an empty repository on github.com first (no README), then:
git remote add origin https://github.com/<your-username>/dormmeal.git
git push -u origin main
```
Commits were made with a placeholder e-mail. Set yours first if needed:
`git config user.email "you@example.com"` (applies to future commits).
