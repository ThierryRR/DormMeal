"""Free-text event -> Event, and how an event changes the constraints.

Examples: "the tuna kimbap was sold out at GS25", "I'll skip dinner on Friday",
"my budget is now 40,000 won", "the microwave in my dorm is broken".
The LLM is tried first (validated JSON); deterministic rules are the fallback.
"""
import difflib
import re
from typing import Iterable, Optional

from pydantic import BaseModel

from . import llm
from .models import Constraints, Equipment, Event, MealPlan, MealSlot, Product, Store
from .parser import parse_budget

DAYS = {"monday": 1, "mon": 1, "tuesday": 2, "tue": 2, "wednesday": 3, "wed": 3, "thursday": 4, "thu": 4,
        "friday": 5, "fri": 5, "saturday": 6, "sat": 6, "sunday": 7, "sun": 7}


def _day(text: str, today: Optional[int]) -> Optional[int]:
    t = text.lower()
    m = re.search(r"\bday\s*([1-7])\b", t)
    if m:
        return int(m.group(1))
    for w, d in DAYS.items():
        if re.search(rf"\b{w}\b", t):
            return d
    if today and re.search(r"\b(today|tonight)\b", t):
        return today
    if today and "tomorrow" in t:
        return min(7, today + 1)
    return None


def _slot(text: str) -> Optional[MealSlot]:
    t = text.lower()
    for s, words in ((MealSlot.BREAKFAST, ["breakfast", "morning"]), (MealSlot.LUNCH, ["lunch", "noon"]),
                     (MealSlot.DINNER, ["dinner", "supper", "tonight", "evening"])):
        if any(re.search(rf"\b{w}\b", t) for w in words):
            return s
    return None


def match_product(text: str, candidates: Iterable[Product]) -> Optional[Product]:
    """Find the product the user is talking about (id, or closest English name)."""
    candidates = list(candidates)
    t = text.lower()
    for p in candidates:
        if p.product_id.lower() in t:
            return p
    best, best_score = None, 0.0
    words = set(re.findall(r"[a-z0-9]+", t))
    for p in candidates:
        name = p.name_en.lower()
        overlap = len(words & set(re.findall(r"[a-z0-9]+", name))) / max(1, len(set(name.split())))
        score = overlap + 0.5 * difflib.SequenceMatcher(None, t, name).ratio()
        if score > best_score:
            best, best_score = p, score
    return best if best_score >= 0.6 else None


def parse_event_rules(text: str, plan: Optional[MealPlan], catalog: list[Product],
                      today: Optional[int] = None) -> Optional[Event]:
    t = text.lower()
    store = next((s for s, w in ((Store.CU, r"\bcu\b"), (Store.GS25, r"\bgs ?25\b"),
                                 (Store.EMART24, r"\bemart ?24\b"),
                                 (Store.SEVEN_ELEVEN, r"\b(?:7-?eleven|seven ?eleven)\b")) if re.search(w, t)), None)
    if re.search(r"sold out|out of stock|not available|no more|couldn't find|could not find|wasn't there", t):
        in_plan = {i.product_id for m in plan.meals for i in m.items} if plan else set()
        pool = [p for p in catalog if p.product_id in in_plan] or catalog
        if store:
            pool = [p for p in pool if p.store == store] or pool
        p = match_product(text, pool)
        return Event(type="sold_out", product_id=p.product_id if p else None,
                     store=p.store if p else store, raw_text=text)
    for eq in Equipment:
        if eq.value in t or (eq == Equipment.FRIDGE and "refrigerator" in t):
            lost = re.search(r"broken|not working|doesn't work|does not work|no longer|lost|removed|can't use|taken", t)
            gained = re.search(r"\b(got|bought|have now|now have|new|fixed|repaired|works again)\b", t)
            if lost or gained:
                return Event(type="equipment_change", equipment=eq, available=bool(gained and not lost), raw_text=text)
    if re.search(r"budget|won|krw|₩|만원|\d+k\b", t):
        b = parse_budget(text)
        if b:
            return Event(type="budget_change", new_budget_krw=b, raw_text=text)
    if re.search(r"skip|won't eat|will not eat|not eat|eating out|eat out|dinner with|lunch with|cafeteria|restaurant", t):
        day, slot = _day(text, today), _slot(text)
        if day and slot:
            return Event(type="skip_meal", day=day, slot=slot, raw_text=text)
    return None


SYSTEM = """Convert a student's message about their weekly meal plan into JSON with keys:
type ("skip_meal" | "sold_out" | "budget_change" | "equipment_change"), day (1-7, Monday=1, or null),
slot ("breakfast" | "lunch" | "dinner" or null), product_id (from the list or null), store (CU | GS25 | Emart24 | 7-Eleven or null),
new_budget_krw (integer or null), equipment ("microwave" | "kettle" | "fridge" or null),
available (true if the equipment was gained/fixed, false if lost/broken, else null).
Output only JSON. Use only product_ids from this list:
"""


def parse_event(text: str, plan: Optional[MealPlan], catalog: list[Product], today: Optional[int] = None,
                use_llm: bool = True) -> Optional[Event]:
    rules = parse_event_rules(text, plan, catalog, today)
    if use_llm and llm.available():
        in_plan = sorted({i.product_id for m in plan.meals for i in m.items}) if plan else []
        by_id = {p.product_id: p for p in catalog}
        listing = "\n".join(f"{pid}: {by_id[pid].name_en} ({by_id[pid].store.value})" for pid in in_plan)
        user = f"Today is day {today}.\n{text}" if today else text
        data = llm.complete_model(SYSTEM + listing, user, _EventIn)
        if data is not None and (data.product_id is None or data.product_id in by_id):
            return Event(raw_text=text, **data.model_dump())
    return rules



class _EventIn(BaseModel):
    type: str
    day: Optional[int] = None
    slot: Optional[MealSlot] = None
    product_id: Optional[str] = None
    store: Optional[Store] = None
    new_budget_krw: Optional[int] = None
    equipment: Optional[Equipment] = None
    available: Optional[bool] = None


def apply_event(c: Constraints, e: Event) -> tuple[Constraints, str]:
    """Return updated constraints and a one-line description of the change."""
    c = c.model_copy(deep=True)
    if e.type == "sold_out" and e.product_id:
        c.unavailable_product_ids = sorted(set(c.unavailable_product_ids) | {e.product_id})
        return c, f"{e.product_id} is marked as sold out for the rest of the week."
    if e.type == "skip_meal" and e.day and e.slot:
        if (e.day, e.slot) not in c.skipped_meals:
            c.skipped_meals = c.skipped_meals + [(e.day, e.slot)]
        return c, f"Day {e.day} {e.slot.value} is skipped."
    if e.type == "budget_change" and e.new_budget_krw:
        c.weekly_budget_krw = e.new_budget_krw
        return c, f"Weekly budget changed to {e.new_budget_krw:,} KRW."
    if e.type == "equipment_change" and e.equipment is not None:
        eq = set(c.equipment)
        eq = eq | {e.equipment} if e.available else eq - {e.equipment}
        c.equipment = sorted(eq, key=lambda x: x.value)
        return c, f"{e.equipment.value} is now {'available' if e.available else 'unavailable'}."
    return c, "The event could not be applied (missing details)."
