# Catalog data collection guide

Goal: a catalog where most rows are `verified = true`.

Status (2026-11-12): 378 products = 145 sourced (workbook + official KCA prices + a few Open Food Facts records),
83 real products with an official KCA price and estimated nutrition, 150 generic estimates. Built by `scripts/import_excel.py`.
Priority gaps: **allergen lines** (missing for all sourced rows) and **protein foods** (eggs, chicken breast, tofu,
salads, more dosirak), which are absent from the sourced data.

## For each product, record
| Column | How to get it |
|---|---|
| `product_id` | Chain prefix + number (CU018, GS018, EM017...), unique |
| `name_en` | Your own English name, short and recognisable |
| `store`, `category` | `CU` / `GS25` / `Emart24`; reuse existing categories when possible |
| `price_krw` | Shelf price tag (integer, KRW) |
| `promo_type` | `none`, `1+1` or `2+1` as shown on the tag |
| `kcal`, `protein_g`, `carbs_g`, `fat_g`, `sodium_mg` | Nutrition label. **Check whether values are per pack or per 100 g** and convert to the whole pack |
| `allergens` | Allergen line on the pack, lower case, `;` separated (egg;soy;wheat;milk;fish;pork;beef;chicken;nuts) |
| `diet_tags` | `vegetarian` only if the ingredient list clearly has no meat or fish. Do **not** tag `halal_friendly` unless certified |
| `requires` | `microwave`, `kettle`, `fridge` (equipment to prepare or store) |
| `prep_instructions` | Copy the heating instruction (e.g. "Microwave 2 min"). Mandatory if `requires` has microwave or kettle |
| `description` | Packaging colour, shelf section: helps find it in an English-only interface |
| `last_updated` | Date of observation (YYYY-MM-DD) |
| `verified` | `true` only when price and nutrition come from an identified source for this exact product (label/tag photo, MFDS record, manufacturer page, retailer catalog). Never for estimates |
| `source` | URL or `label photo 2026-11-05, CU <store name>`, plus confidence level. Required when `verified = true` |
| `name_ko` | Korean name exactly as printed (lets an English-speaking user match the package) |
| `allergens_known` | `false` when the source gives no allergen line: the product is then excluded for any allergic user |

## Workflow
1. Take photos of the price tag and nutrition label in store (or note them), 20-30 products per visit.
2. Add rows to the workbook (preferred, then run `python scripts/import_excel.py`) or directly to `data/catalog.csv`.
3. Run `python scripts/validate_catalog.py` to see progress and detect typos (kcal vs macros, missing prep, duplicates).
4. Run `pytest -q`, then commit (`data: add N verified products from <chain>`).

## Tips
- Cover the categories the planner needs: protein (eggs, chicken breast, tofu), carbs (rice, bread), vegetables and fruit, dairy, drinks, plus a few cheap fillers.
- Prices and promos change monthly: re-check promo items before the benchmark (week 7) and update `last_updated`.
- Never overwrite a verified row with an estimate.
- Report the share of verified products in the final report (the validation script prints it).
