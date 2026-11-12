# Changelog

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
