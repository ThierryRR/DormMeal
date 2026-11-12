# DormMeal: final report (draft)

*Author: Rosano Thierry. Draft generated from the repository state of 2026-11-12. Sections marked
**[TO DO]** need results that only the author can produce (real labels, real users, live LLM runs).*

## 1. Problem
International students in Korean dorms often eat from convenience stores. They face four problems at the
same time: a tight budget, Korean-only labels (allergens, preparation), limited equipment (shared
microwave, kettle, sometimes no fridge) and poor nutrition (a Korea Consumer Agency test found 760-1,393 mg
of sodium per convenience-store kimbap roll, 38-70% of the 2,000 mg daily reference). Promotions (1+1, 2+1)
lower the cost but make planning harder.

## 2. Solution
DormMeal plans a week of convenience-store meals under the user's budget, allergies, diet, equipment and
stores, and replans after events (sold out, skipped meal, new budget, broken microwave).
Main claim: **an LLM never produces a number or a safety decision.** The LLM (Gemini) only turns free text
into validated structured data; a CP-SAT optimizer builds the plan; a Verifier checks it.

## 3. System
See `docs/ARCHITECTURE.md`. Workflow: parse -> search -> optimize -> verify -> explain; replanning locks
the meals already eaten and re-optimizes the rest with a stability bonus. Interface: Streamlit.
Data: 248 products in 4 chains (CU, GS25, 7-Eleven, Emart24). **98 are sourced** from a research workbook
(MFDS-matched nutrition, manufacturer/retailer pages, Meokfit reference prices; URL and confidence level per row);
**150 are estimates**. Users can restrict planning to sourced products. SQLite stores users, plans, likes, events.

## 4. Evaluation
### 4.1 Tests
79 automated tests, including two property tests: `search_catalog` never returns an unsafe product, and the
optimizer never returns a plan with a hard-constraint violation (random budgets, allergies, equipment,
diets, stores, meals per day).

### 4.2 Benchmark (12 seeded scenarios, same Verifier)
| Planner | Fully valid | Hard constraints respected | Comment |
|---|---|---|---|
| DormMeal | 1/12 | 10/10 plans returned; 2 refused with an explanation | failures are nutrition gaps at low budgets |
| LLM-only (Gemini) | **[TO DO]** | **[TO DO]** | run `python benchmark/run_benchmark.py` with `GEMINI_API_KEY` |

### 4.3 Budget sensitivity
With a microwave, about **80,000 KRW per week** meets every daily target; without equipment about 90,000 KRW is
needed, and with sourced products only about 100,000 KRW (`docs/EVALUATION.md`). Equipment matters more than a vegetarian diet. A wheat
allergy leaves too few main dishes for 21 meals: DormMeal says so instead of returning an unsafe plan.

### 4.4 Simulated focus group (week 10)
**[TO DO]** after the live run of `notebooks/W10_DormMeal_RAG_FocusGroup.ipynb`: main needs and concerns,
one unrealistic moment, quotes.

### 4.5 Real users
**[TO DO]** 3-5 dorm students use the app for one week. Suggested checks:
1. Can they find each product in the store from the English description? (found / not found per item)
2. Would they actually eat the planned meals? (rate each day 1-5; note rejected products)
3. Is the weekly cost close to what they paid? (receipt vs plan)
4. Is giving allergies and equipment acceptable? What would make them stop using it?

## 5. Limitations
- **Data:** 98 of 248 products are sourced (39.5%); 150 are still estimates. Sourced rows have **no allergen data**
  (excluded for allergic users) and **no plain protein foods** (eggs, chicken breast, tofu), so sourced-only plans
  often miss the protein target. Prices are catalog reference prices, not shelf prices observed in one store.
- **Optimality:** the search is time-limited (20 s); plans are good, not always optimal.
- **Coverage:** only 1+1 and 2+1 promos; no halal certification data; prices vary by store and month.
- **Persistence on the free hosting tier** is not durable.

## 6. Next steps
1. Complete the data: allergen lines for the 98 sourced products, then protein foods and lunch boxes (labels in store,
   or the MFDS Open API with a free data.go.kr key).
2. Run the LLM-only benchmark and the live notebook; fill sections 4.2 and 4.4.
3. Test with real students (section 4.5) and adjust meal rules and explanations.
