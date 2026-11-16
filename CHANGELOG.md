# Changelog

## [1.3.0] - 2026-11-16
### Added
- FatSecret Korea brand records (`data/sources/fatsecret_matches.json`): real kcal, protein, carbs and fat for 86
  price-only rows (sodium and allergens still estimated) and carbs/fat for 5 workbook rows that lacked them.
- Catalog: 390 products = 150 sourced + 90 price-only + 150 generic estimates.
- `scripts/infer_allergens.py`: informational allergen list from Korean product names (allergens_known stays false).
### Changed
- Several earlier estimates were wrong and are now replaced by source values (e.g. Selex protein drink 99 kcal,
  Powerade 60 kcal per 600 ml).

## [1.2.0] - 2026-11-12
### Added
- Official KCA convenience-store price survey (460 prices, price.go.kr, 2026-11-06) and Open Food Facts matches
  in `data/sources/`.
- Catalog grows to 378 products: 145 sourced (+35 KCA-priced rows, +12 KCA + Open Food Facts rows),
  83 real products with official price and estimated nutrition, 150 generic estimates.
- Optimizer: at most one snack / ice cream per day.
### Not re-run
- Benchmark and budget sensitivity (still computed on the 248-product catalog).

## [1.1.0] - 2026-11-12
### Added
- 98 sourced products imported from the research workbook (`scripts/import_excel.py`, `data/catalog_sourced.csv`,
  `data/IMPORT_REPORT.md`); `data/catalog.csv` = sourced + estimated products (248).
- 7-Eleven chain, `name_ko`, `allergens_known`, `sourced_only` option (UI checkbox), data badge in the shopping list.
- 5 tests (79 in total).
### Changed
- Products with unknown allergens are excluded for allergic users (search and Verifier).
- App, benchmark and scripts use `data/catalog.csv`.

## [1.0.0] - 2026-11-12
### Added
- Verifier and CP-SAT optimizer (week 3), request parser and agent workflow (week 4), replanning and
  persistence (week 5), Streamlit UI (week 6), benchmark (week 7), Docker / Streamlit Cloud (week 8),
  robustness tests (week 9), week-10 lab notebook, evaluation (week 11), documentation (week 12),
  final report draft and demo script (week 13).
- 74 tests in total.
### Known gaps
- Catalog still 0% verified; LLM-only benchmark and notebook live run require a Gemini key.

## [0.3.0] - 2026-11-12
### Added
- Catalog extended from 50 to 150 products (50 per chain, 21 categories, 25 promos).
  New rows are estimates of typical label values: `verified = false`, `source` says so.
- `notebooks/W10_DormMeal_RAG_FocusGroup.ipynb`: week-10 lab (RAG project agent + simulated focus group).
### Known gaps
- Still 0% verified: values must be replaced by real label/shelf readings.

## [0.2.0] - 2026-11-02
### Added
- `source` field on products (model, CSV, SQLite) for data traceability.
- `dormmeal/validation.py` and `scripts/validate_catalog.py`: catalog progress and quality report
  (duplicates, kcal vs macros, sodium/price outliers, missing prep instructions, verified without source).
- `data/catalog_template.csv` (header only) and `docs/DATA_COLLECTION_GUIDE.md`.
- 3 tests for the validation module and the `source` column (31 tests total).
- `docs/DEVELOPMENT_LOG.md`: report-ready description of the work, decisions and sources.
### Changed
- `db.py`: product INSERT now lists column names explicitly (safer when the schema evolves).
- Promo rule confirmed against public sources (see development log); documented limits (1+2 promos not modelled).
- README updated.
### Known gaps
- Catalog values are still estimates (`verified = false` for all 50 rows); target is ~150 products.

## [0.1.0] - 2026-11-02
### Added
- Project skeleton, CI (GitHub Actions + pytest), Pydantic schemas, SQLite schema and catalog import.
- Starter catalog v1 (50 products, CU / GS25 / Emart24).
- `search_catalog` and `compute_totals` with 1+1 / 2+1 promo logic.
- 28 tests (unit + Hypothesis property test).
