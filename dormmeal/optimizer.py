"""CP-SAT optimizer: builds a 7-day plan from catalog products.

Hard constraints: only products returned by `search_for_constraints` (allergens, equipment, diet,
stores, dislikes), weekly budget with 1+1 / 2+1 promos applied to the weekly quantity, at most
`max_repeats_per_product` meals per product, 1 to 3 different products per meal, locked meals kept.
Soft constraints (penalised): daily kcal range, protein minimum and sodium maximum, so that the
solver still returns the closest plan when the targets cannot all be met within the budget. The
Verifier then reports any remaining nutrition gap to the user.
"""
from dataclasses import dataclass, field
from typing import Iterable, Optional

from ortools.sat.python import cp_model

from .models import Constraints, Meal, MealPlan, MealSlot, PlanItem, Product, PromoType
from .tools import search_for_constraints
from .verifier import day_factor, expected_meals

MAX_UNITS_PER_ITEM = 2
MAX_ITEMS_PER_MEAL = 3
MIN_MEAL_KCAL = 250
W_NUTRITION = 50      # KRW-equivalent penalty per kcal / 0.1 g protein / mg sodium outside targets
LIKE_BONUS = 300      # KRW-equivalent bonus each time a liked product is used
MARGIN_KCAL, MARGIN_PROTEIN_DG, MARGIN_SODIUM = 40, 30, 100   # safety margins (kcal, 0.1 g, mg)


@dataclass
class OptimizeResult:
    status: str                       # optimal | feasible | infeasible
    plan: Optional[MealPlan] = None
    message: str = ""
    nutrition_penalty: int = 0
    candidates: list[str] = field(default_factory=list)


def optimize(catalog: Iterable[Product], c: Constraints, locked: Optional[list[Meal]] = None,
             time_limit_s: float = 12.0, enforce_budget: bool = True) -> OptimizeResult:
    catalog = list(catalog)
    by_id = {p.product_id: p for p in catalog}
    locked = [m for m in (locked or []) if m.items]
    locked_keys = {(m.day, m.slot.value) for m in locked}
    meals = sorted(expected_meals(c) - locked_keys)
    cands = search_for_constraints(catalog, c)
    if not cands and meals:
        return OptimizeResult("infeasible", message="No product matches your allergies, diet, equipment and stores.")
    pids = [p.product_id for p in cands]
    involved = set(pids) | {i.product_id for m in locked for i in m.items}

    model = cp_model.CpModel()
    x, y = {}, {}
    for k in meals:
        for pid in pids:
            x[k, pid] = model.NewIntVar(0, MAX_UNITS_PER_ITEM, f"x_{k}_{pid}")
            y[k, pid] = model.NewBoolVar(f"y_{k}_{pid}")
            model.Add(x[k, pid] <= MAX_UNITS_PER_ITEM * y[k, pid])
            model.Add(x[k, pid] >= y[k, pid])
        model.Add(sum(y[k, pid] for pid in pids) >= 1)
        model.Add(sum(y[k, pid] for pid in pids) <= MAX_ITEMS_PER_MEAL)
        model.Add(sum(int(round(by_id[pid].kcal)) * x[k, pid] for pid in pids) >= MIN_MEAL_KCAL)

    locked_units = {pid: 0 for pid in involved}
    locked_meals_count = {pid: 0 for pid in involved}
    for m in locked:
        for it in m.items:
            locked_units[it.product_id] += it.quantity
        for pid in {it.product_id for it in m.items}:
            locked_meals_count[pid] += 1

    # weekly quantities, promos and budget
    cost_terms = []
    for pid in sorted(involved):
        p = by_id[pid]
        q_expr = sum(x[k, pid] for k in meals if (k, pid) in x) + locked_units[pid]
        n_meals = sum(y[k, pid] for k in meals if (k, pid) in y) + locked_meals_count[pid]
        if pid in pids:
            model.Add(n_meals <= max(c.max_repeats_per_product, locked_meals_count[pid]))
        ub = MAX_UNITS_PER_ITEM * len(meals) + locked_units[pid]
        q = model.NewIntVar(0, ub, f"q_{pid}")
        model.Add(q == q_expr)
        paid = model.NewIntVar(0, ub, f"paid_{pid}")
        if p.promo_type == PromoType.ONE_PLUS_ONE:
            model.Add(2 * paid >= q)
        elif p.promo_type == PromoType.TWO_PLUS_ONE:
            free = model.NewIntVar(0, ub, f"free_{pid}")
            model.Add(3 * free <= q)
            model.Add(paid == q - free)
        else:
            model.Add(paid == q)
        cost_terms.append(p.price_krw * paid)
    cost = sum(cost_terms)
    if enforce_budget:
        model.Add(cost <= c.weekly_budget_krw)

    # daily nutrition (soft)
    t = c.targets
    slacks = []
    for day in range(1, 8):
        f = day_factor(c, day)
        if f == 0:
            continue
        day_meals = [k for k in meals if k[0] == day]
        day_locked = [m for m in locked if m.day == day]

        def total(attr, scale=1):
            var = sum(int(round(getattr(by_id[pid], attr) * scale)) * x[k, pid] for k in day_meals for pid in pids)
            const = sum(int(round(getattr(by_id[i.product_id], attr) * scale)) * i.quantity
                        for m in day_locked for i in m.items)
            return var + const

        kcal, prot, sod = total("kcal"), total("protein_g", 10), total("sodium_mg")
        under_k = model.NewIntVar(0, 10000, f"uk{day}")
        over_k = model.NewIntVar(0, 10000, f"ok{day}")
        under_p = model.NewIntVar(0, 10000, f"up{day}")
        over_s = model.NewIntVar(0, 20000, f"os{day}")
        # targets are tightened by a small margin so that a near-optimal plan still passes the Verifier
        model.Add(kcal + under_k >= int(t.kcal_per_day[0] * f) + MARGIN_KCAL)
        model.Add(kcal - over_k <= int(t.kcal_per_day[1] * f) - MARGIN_KCAL)
        model.Add(prot + under_p >= int(t.protein_g_per_day_min * 10 * f) + MARGIN_PROTEIN_DG)
        model.Add(sod - over_s <= int(t.sodium_mg_per_day_max * f) - MARGIN_SODIUM)
        slacks += [under_k, over_k, under_p, over_s]

    liked = [y[k, pid] for k in meals for pid in pids if pid in c.liked_product_ids]
    penalty = sum(slacks) if slacks else 0

    model.Minimize(W_NUTRITION * penalty + cost - LIKE_BONUS * sum(liked))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = 4
    solver.parameters.random_seed = 7
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        msg = "No plan fits the weekly budget with your constraints."
        if enforce_budget:
            cheapest = optimize(catalog, c, locked, time_limit_s, enforce_budget=False)
            if cheapest.plan is not None:
                from .tools import compute_totals
                need = compute_totals(cheapest.plan, catalog).total_cost_krw
                msg += f" The closest plan to your nutrition targets costs about {need:,} KRW."
        return OptimizeResult("infeasible", message=msg, candidates=pids)

    out = list(locked)
    for k in meals:
        items = [PlanItem(product_id=pid, quantity=int(solver.Value(x[k, pid])))
                 for pid in pids if solver.Value(x[k, pid]) > 0]
        out.append(Meal(day=k[0], slot=MealSlot(k[1]), items=items))
    order = {s.value: i for i, s in enumerate(MealSlot)}
    out.sort(key=lambda m: (m.day, order[m.slot.value]))
    return OptimizeResult("optimal" if status == cp_model.OPTIMAL else "feasible",
                          plan=MealPlan(meals=out),
                          nutrition_penalty=int(sum(solver.Value(s) for s in slacks)), candidates=pids)
