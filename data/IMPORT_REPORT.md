# Import report: research workbook -> DormMeal catalog

Source: `data/sources/base_convenience_stores_coree_v9.xlsx` (sheet MASTER_DATABASE, 150 store-product rows).

- Sourced products in the catalog: **145** = 98 workbook rows with price + kcal + protein + carbs + fat + sodium, + 35 store-product rows added with official KCA prices (price.go.kr survey of 2026-11-06; nutrition from the workbook row of the same product)
- Including 12 store-product rows with official KCA prices and Open Food Facts nutrition (crowd-sourced, confidence C)
- Price difference: GS25 오뚜기밥: workbook 2000 KRW, KCA 2400 KRW
- Left out, no price in the workbook: 43
- Left out, carbs/fat not given: 9
- Per store: {'CU': 65, 'GS25': 32, '7-Eleven': 26, 'Emart24': 22}
- Per category: {'snack': 27, 'drink': 48, 'instant_noodle': 23, 'bento': 5, 'dairy': 11, 'ice_cream': 20, 'kimbap_roll': 2, 'triangle_kimbap': 1, 'sandwich': 4, 'instant_rice': 4}
- With a 1+1 / 2+1 promotion: 10

Nothing was estimated. Allergens are not given in the workbook, so every imported product has `allergens_known = false` and is excluded for users who declare an allergy. Vegetarian status is not documented, so no diet tag is set. Preparation hints are generic, derived from the product type.

`data/catalog.csv` (378 products) = these 145 sourced products + 83 real products with an official KCA price but estimated nutrition (`verified = false`, ids KCP-) + 150 fully estimated generic products (`verified = false`, from `catalog_v1.csv`). The app can be restricted to sourced products only.
