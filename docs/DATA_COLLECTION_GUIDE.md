# Catalog data collection guide

Goal: move from the 50 starter estimates to ~150 products where most rows are `verified = true`.

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
| `verified` | `true` only when price and nutrition come from the real label or tag |
| `source` | e.g. `label photo 2026-11-05, CU <store name>`. Required when `verified = true` |

## Workflow
1. Take photos of the price tag and nutrition label in store (or note them), 20-30 products per visit.
2. Add rows to `data/catalog_v1.csv` (use `data/catalog_template.csv` for the header).
3. Run `python scripts/validate_catalog.py` to see progress and detect typos (kcal vs macros, missing prep, duplicates).
4. Run `pytest -q`, then commit (`data: add N verified products from <chain>`).

## Tips
- Cover the categories the planner needs: protein (eggs, chicken breast, tofu), carbs (rice, bread), vegetables and fruit, dairy, drinks, plus a few cheap fillers.
- Prices and promos change monthly: re-check promo items before the benchmark (week 7) and update `last_updated`.
- Never overwrite a verified row with an estimate.
- Report the share of verified products in the final report (the validation script prints it).
