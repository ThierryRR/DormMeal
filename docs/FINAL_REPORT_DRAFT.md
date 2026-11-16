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
Data: 378 products in 4 chains (CU, GS25, 7-Eleven, Emart24). **145 are sourced** (research workbook with
MFDS-matched nutrition and manufacturer pages; official KCA price survey of 2026-11-06; a few Open Food Facts
records; URL and confidence level per row). **83 are real products with an official price but estimated
nutrition**, and **150 are generic estimates**. Users can restrict planning to sourced products. SQLite stores users, plans, likes, events.

## 4. Evaluation
### 4.1 Tests
105 automated tests (79 original + 26 LLM/RAG tests added in Week 10), including two property tests:
`search_catalog` never returns an unsafe product, and the optimizer never returns a plan with a
hard-constraint violation (random budgets, allergies, equipment, diets, stores, meals per day).

The 26 new tests in `tests/test_llm_rag.py` cover:
- **RAG retrieval quality** (Hit@3 = 5/5 on known-answer questions, out-of-scope questions score < 0.6).
- **Chunk index sanity** (unique IDs, `[doc-n]` convention, ≥ 3 chunks per document, passage format).
- **Agent loop wiring** in MOCK mode (keys present, citations match the index, no hallucinated chunk IDs).
- **Benchmark Verifier integration** (equipment, allergen and budget violations all detected correctly).
- **Prompt-injection safety** (adversarial instruction strings score < 0.5 against any KB chunk).
- **Focus group wiring** (persona card completeness, transcript line count and speaker format).

### 4.2 Benchmark (12 seeded scenarios, same Verifier)
Scenarios: seed 42, budgets 45k–90k KRW, 2–3 meals/day, varied equipment, allergies, diet. Time limit 15 s.
Both planners are scored by the same Verifier. *Valid* = zero violations; *hard constraints OK* = no allergen,
equipment, diet, store, budget, variety or structure violation (nutrition gaps allowed).

| Planner | Valid | Hard constraints OK | Plans returned | Avg time (s) | Main violations |
|---|---|---|---|---|---|
| DormMeal | 16.7% (2/12) | 66.7% (8/12) | 66.7% (8/12; 4 refused with explanation) | 17.8 s | nutrition gaps at low budgets |
| LLM-only (Gemini `gemini-3.1-flash-lite`) | 0% (0/12) | 0% (0/12) | 100% (12/12) | 3.1 s | equipment: 62, nutrition: 133, variety: 13, budget: 10, allergen: 7, store: 5 |

**Notes on DormMeal results.** The 4 refused plans (hard_ok = False) are correct: 3 arise from no-equipment
scenarios with ≤ 45 k KRW (too few eligible products for 21 meals) and 1 from a wheat-allergy/GS25-only
scenario with no main dishes. DormMeal explains each refusal instead of returning an unsafe plan. Nutrition
violations occur because protein-rich foods are mostly in the estimated-nutrition tier (not sourced), and
the catalog has very few eggs or chicken-breast products.

### 4.3 Budget sensitivity
With a microwave, about **80,000 KRW per week** meets every daily target; without equipment about 90,000 KRW is
needed, and with sourced products only about 100,000 KRW (`docs/EVALUATION.md`). Equipment matters more than a vegetarian diet. A wheat
allergy leaves too few main dishes for 21 meals: DormMeal says so instead of returning an unsafe plan.

### 4.4 Simulated focus group (week 10)
Notebook: `notebooks/W10_DormMeal_RAG_FocusGroup.ipynb`. The notebook has two parts.

**Part A — RAG project agent.** A 7-document knowledge base (proposal, promos, constraints, catalog,
data_quality, replanning, roadmap; 25 chunks total) is indexed with TF-IDF (60-word chunks, 15-word overlap).
An LLM agent calls `search_documents` up to 3 times before answering, cites chunk IDs, and says "the project
documents do not specify this" when no passage covers the question. Live run confirmed Hit@3 = 5/5 on known-
answer questions; out-of-scope question ("How many students tested the prototype?") scored 0.18. On the
2+1 budget question, RAG ON cited `[promos-1]` and `[data_quality-2]` and correctly qualified that the
formula was only partially specified in the KB; RAG OFF gave a confident arithmetic example (4,000 KRW for
3 units) with no citation — plausible but unverifiable against project specifications.

**Part B — simulated focus group.** Four participants selected: P03 (international, CS, early adopter,
300 k/month), P05 (economics, privacy-conscious, 400 k/month), P07 (exchange student, design, kettle only,
500 k/month), P09 (data science, night-shift worker, quits long setups, 380 k/month). Three discussion
questions covered: (1) last convenience-store experience and what went wrong, (2) variety vs. cost trade-off,
(3) data comfort (allergies, budget, equipment).

**Live run results (Gemini `gemini-3.1-flash-lite`).** Key quotes:

- *P07 on the language barrier:* "My biggest struggle is the language barrier; I often can't read the nutritional info on packaging, so I just guess." — directly motivates the English-first design.
- *P09 on friction:* "I'd use DormMeal if the setup is zero-touch — no manual entry. If it can pull real-time inventory and calculate the most efficient path for my 380,000 KRW budget without a tedious onboarding process, it's worth testing."
- *P05 on privacy:* "I'll delete the app immediately if it requests access to my contacts, location, or photos. Those permissions are irrelevant to meal planning and suggest data harvesting."
- *P03 on variety:* "At 300,000 KRW, variety is a luxury I can't afford. The app needs to pull real-time API data from GS25 or CU apps to be viable."

**One unrealistic moment.** All four personas independently converge on near-identical phrasing ("set it and forget it", "pull real-time API data from convenience store apps", "fully automated") across separate turns. Real focus-group participants vary in vocabulary and emphasis; this uniformity is a hallucination artifact — the LLM echoes the same design concern in four voices instead of four genuinely different ones. The substance (friction concern) is realistic; the identical wording is not.

### 4.5 Real users
**[TO DO]** 3-5 dorm students use the app for one week. Suggested checks:
1. Can they find each product in the store from the English description? (found / not found per item)
2. Would they actually eat the planned meals? (rate each day 1-5; note rejected products)
3. Is the weekly cost close to what they paid? (receipt vs plan)
4. Is giving allergies and equipment acceptable? What would make them stop using it?

## 5. Limitations
- **Data:** 145 of 378 products are sourced (38%); 233 have estimated nutrition (83 of them with an official price). Sourced rows have **no allergen data**
  (excluded for allergic users) and **no plain protein foods** (eggs, chicken breast, tofu), so sourced-only plans
  often miss the protein target. Prices are catalog reference prices, not shelf prices observed in one store.
- **Optimality:** the search is time-limited (20 s); plans are good, not always optimal.
- **Coverage:** only 1+1 and 2+1 promos; no halal certification data; prices vary by store and month.
- **Persistence on the free hosting tier** is not durable.

## 6. Next steps
1. Complete the data: allergen lines for the 98 sourced products, then protein foods and lunch boxes (labels in store,
   or the MFDS Open API with a free data.go.kr key).
2. Run the live notebook with real participants and paste focus group quotes (section 4.4).
3. Test with real students (section 4.5) and adjust meal rules and explanations.
