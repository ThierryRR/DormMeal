from pathlib import Path

import pytest

from dormmeal import llm
from dormmeal.agent import DormMealAgent
from dormmeal.models import Diet, Equipment, Store
from dormmeal.parser import parse_budget, parse_request, parse_rules
from dormmeal.tools import load_catalog_csv

CSV = Path(__file__).resolve().parent.parent / "data" / "catalog_v1.csv"
CATALOG = load_catalog_csv(CSV)


@pytest.mark.parametrize("text,expected", [
    ("a 35,000 KRW weekly budget", 35000),
    ("budget 50k", 50000),
    ("8000 won a day", 56000),
    ("₩60,000", 60000),
    ("5만원 per week", 50000),
    ("I have 30 000 won", 30000),
    ("2 meals a day, day 3", None),
])
def test_parse_budget(text, expected):
    assert parse_budget(text) == expected


def test_parse_rules_full_request():
    r = parse_rules("budget 50k per week, vegetarian, I'm allergic to milk and eggs, "
                    "I have a fridge and a microwave, only GS25, 2 meals a day")
    c = r.constraints
    assert c.weekly_budget_krw == 50000 and c.diet == Diet.VEGETARIAN
    assert set(c.allergies) == {"milk", "egg"}
    assert set(c.equipment) == {Equipment.MICROWAVE, Equipment.FRIDGE}
    assert c.stores == [Store.GS25] and c.meals_per_day == 2


def test_parse_rules_negated_equipment():
    c = parse_rules("I have a microwave but no kettle, 35,000 KRW, nut allergy").constraints
    assert c.equipment == [Equipment.MICROWAVE] and c.allergies == ["nuts"]


def test_parse_rules_missing_budget():
    r = parse_rules("plan my meals, I can't eat pork")
    assert r.constraints is None and r.missing == ["weekly budget in KRW"]


def test_parse_request_without_key_uses_rules(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    r = parse_request("budget 40000 won, microwave")
    assert not r.used_llm and r.constraints.weekly_budget_krw == 40000


def test_parse_request_falls_back_when_llm_fails(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "complete_model", lambda *a, **k: None)
    r = parse_request("budget 40000 won, microwave")
    assert r.constraints.weekly_budget_krw == 40000
    assert any("LLM parsing failed" in a for a in r.assumptions)


def test_agent_asks_for_budget():
    s = DormMealAgent(CATALOG, use_llm=False).plan("plan my week please")
    assert s.status == "need_info" and "budget" in s.message


def test_agent_infeasible_budget_is_explained():
    s = DormMealAgent(CATALOG, use_llm=False, time_limit_s=3).plan("5,000 won budget, microwave")
    assert s.status == "infeasible" and "at least" in s.message


def test_agent_plans_and_explains():
    a = DormMealAgent(CATALOG, use_llm=False, time_limit_s=8)
    s = a.plan("I have a microwave and a fridge, 80,000 KRW per week, nut allergy")
    assert s.status == "planned" and s.plan is not None
    assert "KRW" in s.message and [t.split(":")[0] for t in s.trace] == ["parse", "search", "optimize", "verify"]
    shop = a.shopping_list(s.plan)
    assert sum(r["cost_krw"] for r in shop) == s.verification.totals.total_cost_krw <= 80000
