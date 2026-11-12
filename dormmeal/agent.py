"""DormMeal agent: a small explicit graph of nodes.

    parse -> (need_info?) -> search -> optimize -> verify -> explain

The design follows the "simplest adequate design" rule: a predictable workflow with one gate
(the Verifier), not a free-form agent loop. The LLM is only used inside `parse` (free text ->
Constraints) and inside event parsing (week 5). Every node appends to `state.trace`.
LangGraph was planned in week 1; an explicit state machine with the same nodes was kept instead
(no extra dependency, easier to test, same behaviour).
"""
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional

from .models import Constraints, Event, MealPlan, MealSlot, Product, VerificationResult
from .optimizer import optimize
from .events import apply_event, parse_event
from .parser import parse_request
from .tools import paid_units, search_for_constraints
from .verifier import day_factor, verify

HARD_RULES = {"unknown_product", "allergen", "equipment", "diet", "store", "preference", "budget",
              "variety", "structure"}


@dataclass
class AgentState:
    request: str = ""
    constraints: Optional[Constraints] = None
    plan: Optional[MealPlan] = None
    verification: Optional[VerificationResult] = None
    status: str = "new"                 # need_info | infeasible | planned | error
    message: str = ""
    assumptions: list[str] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)
    used_llm: bool = False

    def log(self, node: str, info: str, t0: float):
        self.trace.append(f"{node}: {info} ({time.time() - t0:.2f}s)")


class DormMealAgent:
    def __init__(self, catalog: Iterable[Product], use_llm: bool = True, time_limit_s: float = 20.0):
        self.catalog = list(catalog)
        self.by_id = {p.product_id: p for p in self.catalog}
        self.use_llm = use_llm
        self.time_limit_s = time_limit_s

    # ---------------- nodes ----------------
    def plan(self, text: str = "", constraints: Optional[Constraints] = None, locked=None) -> AgentState:
        s = AgentState(request=text)
        t0 = time.time()
        if constraints is None:
            parsed = parse_request(text, use_llm=self.use_llm)
            s.used_llm, s.assumptions = parsed.used_llm, parsed.assumptions
            s.log("parse", f"llm={parsed.used_llm} missing={parsed.missing}", t0)
            if parsed.missing:
                s.status = "need_info"
                s.message = "To build your plan I still need: " + ", ".join(parsed.missing) + \
                            ". Example: 'My budget is 50,000 KRW per week, I have a microwave.'"
                return s
            constraints = parsed.constraints
        s.constraints = constraints
        return self._solve(s, locked)

    def _solve(self, s: AgentState, locked=None, previous: Optional[MealPlan] = None) -> AgentState:
        c = s.constraints
        t0 = time.time()
        n = len(search_for_constraints(self.catalog, c))
        s.log("search", f"{n} compatible products", t0)

        t0 = time.time()
        r = optimize(self.catalog, c, locked=locked, time_limit_s=self.time_limit_s, previous=previous)
        s.log("optimize", f"status={r.status} nutrition_penalty={r.nutrition_penalty}", t0)
        if r.plan is None:
            s.status, s.message = "infeasible", r.message
            return s

        t0 = time.time()
        s.plan = r.plan
        s.verification = verify(r.plan, self.catalog, c)
        hard = [v for v in s.verification.violations if v.rule in HARD_RULES]
        s.log("verify", f"valid={s.verification.valid} violations={len(s.verification.violations)}", t0)
        if hard:  # should never happen: the optimizer enforces them. Do not show an unsafe plan.
            s.status, s.plan = "error", None
            s.message = "Internal check failed: " + "; ".join(v.detail for v in hard)
            return s
        s.status = "planned"
        s.message = self.explain(s)
        return s

    def replan(self, s: AgentState, event, today: int, now: MealSlot) -> AgentState:
        """Apply an event during the week. Meals before (today, now) are locked (already eaten);
        the remaining meals are re-optimised with the updated constraints."""
        t0 = time.time()
        if isinstance(event, str):
            ev = parse_event(event, s.plan, self.catalog, today=today, use_llm=self.use_llm)
        else:
            ev = event
        if ev is None:
            out = AgentState(request=str(event), constraints=s.constraints, plan=s.plan,
                             verification=s.verification, status=s.status, assumptions=s.assumptions)
            out.message = ("I could not understand this change. Try e.g. 'GS25 tuna kimbap was sold out', "
                           "'skip dinner on Friday', 'my budget is now 40,000 won', 'the microwave is broken'.")
            return out
        new_c, desc = apply_event(s.constraints, ev)
        order = {sl.value: i for i, sl in enumerate(MealSlot)}
        cut = (today, order[now.value])
        locked = [m.model_copy(update={"locked": True}) for m in s.plan.meals
                  if (m.day, order[m.slot.value]) < cut]
        # a skipped meal in the past changes nothing
        new_c.skipped_meals = [(d, sl) for d, sl in new_c.skipped_meals
                               if (d, order[MealSlot(sl).value]) >= cut or (d, sl) in s.constraints.skipped_meals]
        out = AgentState(request=ev.raw_text, constraints=new_c, assumptions=s.assumptions, used_llm=s.used_llm)
        out.log("event", f"{ev.type}: {desc}", t0)
        out = self._solve(out, locked=locked, previous=s.plan)
        if out.plan is not None:
            before = {(m.day, m.slot.value): sorted((i.product_id, i.quantity) for i in m.items) for m in s.plan.meals}
            changed = sum(1 for m in out.plan.meals if not m.locked and
                          before.get((m.day, m.slot.value)) != sorted((i.product_id, i.quantity) for i in m.items))
            out.message = f"{desc} {len(locked)} meals already eaten were kept; {changed} upcoming meals changed.\n" \
                          + out.message
        else:
            out.message = f"{desc} " + out.message
        return out

    # ---------------- presentation (deterministic, numbers come from code) ----------------
    def shopping_list(self, plan: MealPlan) -> list[dict]:
        units = defaultdict(int)
        for m in plan.meals:
            for it in m.items:
                units[it.product_id] += it.quantity
        rows = []
        for pid, q in sorted(units.items(), key=lambda kv: (self.by_id[kv[0]].store.value, kv[0])):
            p = self.by_id[pid]
            paid = paid_units(q, p.promo_type)
            rows.append({"store": p.store.value, "product_id": pid, "product": p.name_en, "units": q,
                         "paid_units": paid, "promo": p.promo_type.value, "unit_price_krw": p.price_krw,
                         "cost_krw": paid * p.price_krw, "where": p.description,
                         "prep": p.prep_instructions or "-"})
        return rows

    def meal_rows(self, plan: MealPlan) -> list[dict]:
        rows = []
        for m in plan.meals:
            names = [f"{self.by_id[i.product_id].name_en}" + (f" x{i.quantity}" if i.quantity > 1 else "")
                     for i in m.items]
            kcal = sum(self.by_id[i.product_id].kcal * i.quantity for i in m.items)
            rows.append({"day": m.day, "slot": m.slot.value, "items": " + ".join(names) or "(skipped)",
                         "kcal": round(kcal), "locked": m.locked})
        return rows

    def explain(self, s: AgentState) -> str:
        c, v = s.constraints, s.verification
        tot = v.totals
        shop = self.shopping_list(s.plan)
        saved = sum((r["units"] - r["paid_units"]) * r["unit_price_krw"] for r in shop)
        lines = [f"Your 7-day plan costs {tot.total_cost_krw:,} KRW of your {c.weekly_budget_krw:,} KRW budget "
                 f"({len(shop)} different products, {sum(r['units'] for r in shop)} units)."]
        if saved:
            lines.append(f"1+1 / 2+1 promotions save you {saved:,} KRW (buy promo items in one trip).")
        days = [d for d in range(1, 8) if day_factor(c, d) > 0]
        avg = lambda dct: sum(dct.get(d, 0) for d in days) / max(1, len(days))
        lines.append(f"Average per day: {avg(tot.daily_kcal):.0f} kcal, {avg(tot.daily_protein_g):.0f} g protein, "
                     f"{avg(tot.daily_sodium_mg):.0f} mg sodium.")
        if c.allergies:
            lines.append("Excluded allergens: " + ", ".join(c.allergies) + ".")
        lines.append("Equipment used: " + (", ".join(e.value for e in c.equipment) or "none") + ".")
        gaps = [x.detail for x in v.violations if x.rule == "nutrition"]
        if gaps:
            lines.append(f"Nutrition targets not fully met on {len({g.split(':')[0] for g in gaps})} day(s) with this "
                         f"budget: " + "; ".join(gaps[:3]) + (" ..." if len(gaps) > 3 else "") +
                         ". A higher budget or more equipment (microwave/fridge) usually fixes this.")
        else:
            lines.append("All budget, safety and nutrition checks passed.")
        for a in s.assumptions:
            lines.append(f"Assumption: {a}.")
        n_src = sum(1 for r in shop if self.by_id[r["product_id"]].verified)
        lines.append(f"Data: {n_src} of {len(shop)} products have sourced prices and nutrition; the others are estimates.")
        return "\n".join(lines)
