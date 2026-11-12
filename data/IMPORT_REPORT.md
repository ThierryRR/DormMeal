# Import report: research workbook -> DormMeal catalog

Source: `data/sources/base_convenience_stores_coree_v9.xlsx` (sheet MASTER_DATABASE, 150 store-product rows).

- Imported (price + kcal + protein + carbs + fat + sodium all given): **98**
- Left out, no price: 43
- Left out, carbs/fat not given: 9
- Per store: {'CU': 46, 'GS25': 17, '7-Eleven': 21, 'Emart24': 14}
- Per category: {'snack': 13, 'drink': 41, 'instant_noodle': 11, 'bento': 5, 'dairy': 8, 'ice_cream': 9, 'kimbap_roll': 2, 'triangle_kimbap': 1, 'sandwich': 4, 'instant_rice': 4}
- With a 1+1 / 2+1 promotion: 10

Nothing was estimated. Allergens are not given in the workbook, so every imported product has `allergens_known = false` and is excluded for users who declare an allergy. Vegetarian status is not documented, so no diet tag is set. Preparation hints are generic, derived from the product type.

`data/catalog.csv` = these 98 sourced products + 150 estimated products (`verified = false`) from `catalog_v1.csv`. The app can be restricted to sourced products only.
