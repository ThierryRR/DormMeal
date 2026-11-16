# Import report: research workbook -> DormMeal catalog

Source: `data/sources/base_convenience_stores_coree_v9.xlsx` (sheet MASTER_DATABASE, 150 store-product rows).

- Sourced products in the catalog: **150** = 103 workbook rows with price + kcal + protein + carbs + fat + sodium, + 35 store-product rows added with official KCA prices (price.go.kr survey of 2026-11-06; nutrition from the workbook row of the same product)
- Including 12 store-product rows with official KCA prices and Open Food Facts nutrition (crowd-sourced, confidence C)
- Including 5 workbook rows completed with carbs and fat from FatSecret Korea (confidence C)
- 86 of the 90 price-only rows now have kcal, protein, carbs and fat from FatSecret Korea; only their sodium and allergens are estimates
- Price difference: GS25 오뚜기밥: workbook 2000 KRW, KCA 2400 KRW
- Left out, no price in the workbook: 43
- Left out, carbs/fat not given: 4
- Per store: {'CU': 67, 'GS25': 33, '7-Eleven': 27, 'Emart24': 23}
- Per category: {'snack': 27, 'drink': 52, 'instant_noodle': 24, 'bento': 5, 'dairy': 11, 'ice_cream': 20, 'kimbap_roll': 2, 'triangle_kimbap': 1, 'sandwich': 4, 'instant_rice': 4}
- With a 1+1 / 2+1 promotion: 10

Nothing was estimated. Allergens are not given in the workbook, so every imported product has `allergens_known = false` and is excluded for users who declare an allergy. Vegetarian status is not documented, so no diet tag is set. Preparation hints are generic, derived from the product type.

`data/catalog.csv` (390 products) = these 150 sourced products + 90 real products with an official KCA price, most with FatSecret macros and estimated sodium/allergens (`verified = false`, ids KCP-) + 150 fully estimated generic products (`verified = false`, from `catalog_v1.csv`). The app can be restricted to sourced products only.
