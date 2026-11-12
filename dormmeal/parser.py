"""Free-text request -> Constraints.

`parse_request` tries the LLM first (JSON validated by Pydantic) and falls back to deterministic rules.
The rules also run when the LLM answers, to fill fields the LLM left out, and the result lists which
fields were assumed so the agent can tell the user.
"""
import re
from typing import Optional

from pydantic import BaseModel

from . import llm
from .models import Constraints, Diet, Equipment, Store

ALLERGEN_WORDS = {
    "egg": ["egg", "eggs"],
    "soy": ["soy", "soya", "tofu"],
    "wheat": ["wheat", "gluten"],
    "milk": ["milk", "dairy", "lactose", "cheese"],
    "fish": ["fish", "seafood", "tuna", "salmon", "anchovy", "mackerel"],
    "pork": ["pork", "ham", "spam"],
    "beef": ["beef"],
    "chicken": ["chicken"],
    "nuts": ["nut", "nuts", "peanut", "peanuts", "almond", "almonds"],
}
EQUIPMENT_WORDS = {Equipment.MICROWAVE: ["microwave"], Equipment.KETTLE: ["kettle", "hot water"],
                   Equipment.FRIDGE: ["fridge", "refrigerator"]}
NEG = r"(?:no|without|don't have|do not have|dont have|not have|lack|broken|no access to)"
EXCLUDE_CTX = r"(?:allergic to|allergy to|allergies to|intolerant to|can't eat|cannot eat|can not eat|no|without|avoid)"


class ParsedRequest(BaseModel):
    constraints: Optional[Constraints] = None
    assumptions: list[str] = []
    missing: list[str] = []          # information the agent must ask for (e.g. budget)
    used_llm: bool = False


def _amount(num: str, unit: str) -> int:
    n = float(num.replace(",", ""))
    unit = unit.lower().strip()
    if unit in ("k",):
        n *= 1000
    elif unit in ("만", "만원", "man"):
        n *= 10000
    return int(n)


def parse_budget(text: str) -> Optional[int]:
    t = re.sub(r"(\d)[ .](\d{3})\b", r"\1\2", text.lower())   # "30 000" / "30.000" -> "30000"
    candidates = []
    for m in re.finditer(r"(?:₩\s*)?(\d[\d,]*(?:\.\d+)?)\s*(krw|won|만원|만|원|k(?![a-z]))?", t):
        num, unit = m.group(1), m.group(2) or ""
        val = _amount(num, unit)
        after = t[m.end():m.end() + 25]
        before = t[max(0, m.start() - 25):m.start()]
        if not unit and "budget" not in before + after and val < 1000:
            continue                   # "2 meals", "day 3"
        if val <= 0 or re.match(r"\s*(?:meals?|times?|days?|min|g\b|kcal)", after):
            continue
        per_day = bool(re.match(r"\s*(?:krw|won|원)?\s*(?:per day|a day|/day|daily|each day)", after))
        candidates.append(val * 7 if per_day else val)
    return candidates[0] if candidates else None


def parse_rules(text: str) -> ParsedRequest:
    t = " " + text.lower() + " "
    assumptions, missing = [], []

    budget = parse_budget(text)
    if budget is None:
        missing.append("weekly budget in KRW")

    equipment = []
    for eq, words in EQUIPMENT_WORDS.items():
        for w in words:
            if re.search(rf"\b{w}\b", t):
                if not re.search(rf"{NEG}\s+(?:a\s+|any\s+|the\s+)?(?:\w+\s+)?{w}", t) and \
                        not re.search(rf"{w}\s+(?:is\s+)?(?:broken|not working)", t):
                    equipment.append(eq)
                break
    if not equipment:
        assumptions.append("no kitchen equipment (say 'I have a microwave/kettle/fridge' to unlock more products)")

    allergies = []
    for allergen, words in ALLERGEN_WORDS.items():
        for w in words:
            if re.search(rf"{EXCLUDE_CTX}\s+(?:\w+\s+){{0,3}}?{w}\b", t) or \
                    re.search(rf"\b{w}\s+(?:allergy|allergies|intolerance|free)\b", t) or \
                    re.search(rf"allerg\w*[^.]*\b{w}\b", t):
                allergies.append(allergen)
                break

    diet = Diet.NONE
    if re.search(r"\b(vegetarian|vegan|veggie|no meat)\b", t):
        diet = Diet.VEGETARIAN
    if re.search(r"\bhalal\b", t):
        diet = Diet.HALAL_FRIENDLY

    stores = [s for s, w in ((Store.CU, r"\bcu\b"), (Store.GS25, r"\bgs ?25\b"), (Store.EMART24, r"\bemart ?24\b"),
                                                 (Store.SEVEN_ELEVEN, r"\b(?:7-?eleven|seven ?eleven|세븐일레븐)\b"))
              if re.search(w, t)]
    if not stores:
        stores = list(Store)

    meals = 3
    m = re.search(r"\b([123])\s*meals?\b", t)
    if m:
        meals = int(m.group(1))
    elif re.search(r"skip(?:ping)? breakfast|no breakfast|don't eat breakfast", t):
        meals = 2

    if budget is None:
        return ParsedRequest(constraints=None, assumptions=assumptions, missing=missing)
    c = Constraints(weekly_budget_krw=budget, equipment=equipment, allergies=allergies, diet=diet,
                    stores=stores, meals_per_day=meals)
    return ParsedRequest(constraints=c, assumptions=assumptions, missing=missing)


SYSTEM = """You convert a student's meal-planning request into JSON. Output ONLY a JSON object with keys:
weekly_budget_krw (integer KRW per week, multiply a daily budget by 7, null if not given),
diet ("none" | "vegetarian" | "halal_friendly"),
allergies (list from: egg, soy, wheat, milk, fish, pork, beef, chicken, nuts; include foods the user says they cannot eat),
equipment (list from: microwave, kettle, fridge; only what the user says they HAVE and can use),
stores (list from: CU, GS25, Emart24, 7-Eleven; all four if not restricted),
meals_per_day (1, 2 or 3; default 3)."""


class _LLMRequest(BaseModel):
    weekly_budget_krw: Optional[int] = None
    diet: Diet = Diet.NONE
    allergies: list[str] = []
    equipment: list[Equipment] = []
    stores: list[Store] = list(Store)
    meals_per_day: int = 3


def parse_request(text: str, use_llm: bool = True) -> ParsedRequest:
    rules = parse_rules(text)
    if not (use_llm and llm.available()):
        return rules
    out = llm.complete_model(SYSTEM, text, _LLMRequest)
    if out is None:
        rules.assumptions.append("LLM parsing failed; rule-based parsing used")
        return rules
    budget = out.weekly_budget_krw or (rules.constraints.weekly_budget_krw if rules.constraints else None)
    if not budget:
        return ParsedRequest(missing=["weekly budget in KRW"], used_llm=True, assumptions=rules.assumptions)
    known = set(ALLERGEN_WORDS)
    c = Constraints(weekly_budget_krw=budget, diet=out.diet,
                    allergies=sorted({a.lower() for a in out.allergies if a.lower() in known}),
                    equipment=out.equipment, stores=out.stores or list(Store),
                    meals_per_day=min(3, max(1, out.meals_per_day)))
    assumptions = [] if c.equipment else ["no kitchen equipment (say 'I have a microwave/kettle/fridge')"]
    return ParsedRequest(constraints=c, assumptions=assumptions, used_llm=True)
