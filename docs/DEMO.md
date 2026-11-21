# Demo script (5 minutes)

1. `streamlit run app.py`. Point out the warning: catalog values are estimates.
2. **Form**: 80,000 KRW, microwave + fridge, allergy `nuts`, 3 meals/day -> *Plan my week*.
   Show: cost vs budget, promo savings, week grid, shopping list per store with shelf descriptions,
   nutrition charts, *Checks* tab (all passed) and the agent trace.
3. **Low budget**: 50,000 KRW -> the plan stays within budget, and the Checks tab lists the days that miss
   a nutrition target (soft constraints, honest message).
4. **Impossible case**: 10,000 KRW (the lowest budget the form accepts) -> immediate explanation with the
   minimum cost ("21 meals need at least 18,700 KRW").
5. **Replanning**: Today = Wed, next meal = lunch, "the microwave is broken" -> *Update my plan*: meals
   before Wednesday lunch are kept (locked), later meals no longer need a microwave.
6. **Likes**: dislike a product -> plan again -> it is gone.
7. **Free text** (if a Gemini key is set): "I have 60,000 won, a kettle, I'm vegetarian and skip breakfast."
