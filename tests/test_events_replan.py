from pathlib import Path

import pytest

from dormmeal.agent import DormMealAgent
from dormmeal.db import (get_preferences, import_catalog, init_db, latest_plan, load_user, log_event,
                         save_plan, save_user, set_preference)
from dormmeal.events import apply_event, match_product, parse_event_rules
from dormmeal.models import Constraints, Equipment, Event, MealSlot
from dormmeal.tools import load_catalog_csv

CSV = Path(__file__).resolve().parent.parent / "data" / "catalog_v1.csv"
CATALOG = load_catalog_csv(CSV)
BY_ID = {p.product_id: p for p in CATALOG}


@pytest.mark.parametrize("text,etype", [
    ("the GS25 tuna mayo triangle kimbap was sold out", "sold_out"),
    ("I'll skip dinner on Friday", "skip_meal"),
    ("my budget is now 40,000 won", "budget_change"),
    ("the microwave in my dorm is broken", "equipment_change"),
    ("I bought a kettle", "equipment_change"),
])
def test_parse_event_rules_types(text, etype):
    e = parse_event_rules(text, None, CATALOG, today=3)
    assert e is not None and e.type == etype


def test_parse_event_details():
    assert parse_event_rules("skip lunch tomorrow", None, CATALOG, today=3).day == 4
    e = parse_event_rules("the microwave is broken", None, CATALOG)
    assert e.equipment == Equipment.MICROWAVE and e.available is False
    assert parse_event_rules("the GS25 tuna mayo triangle kimbap was sold out", None, CATALOG).product_id == "GS001"
    assert parse_event_rules("hello there", None, CATALOG) is None


def test_match_product_by_id_and_name():
    assert match_product("EM034 is gone", CATALOG).product_id == "EM034"
    assert match_product("smoked chicken breast pack", [BY_ID["GS017"], BY_ID["CU012"]]).product_id == "GS017"


def test_apply_event():
    c = Constraints(weekly_budget_krw=50000, equipment=[Equipment.MICROWAVE])
    c2, _ = apply_event(c, Event(type="sold_out", product_id="CU001", raw_text=""))
    assert c2.unavailable_product_ids == ["CU001"] and c.unavailable_product_ids == []
    c3, _ = apply_event(c, Event(type="equipment_change", equipment=Equipment.MICROWAVE, available=False, raw_text=""))
    assert c3.equipment == []
    c4, _ = apply_event(c, Event(type="skip_meal", day=2, slot=MealSlot.DINNER, raw_text=""))
    assert (2, MealSlot.DINNER) in c4.skipped_meals


@pytest.fixture(scope="module")
def planned():
    a = DormMealAgent(CATALOG, use_llm=False, time_limit_s=8)
    return a, a.plan("I have a microwave and a fridge, 80,000 KRW per week")


def test_replan_sold_out_keeps_past_and_removes_product(planned):
    a, s = planned
    future = [i.product_id for m in s.plan.meals if m.day >= 4 for i in m.items]
    pid = future[0]
    r = a.replan(s, Event(type="sold_out", product_id=pid, raw_text="sold out"), today=4, now=MealSlot.BREAKFAST)
    assert r.status == "planned"
    past = [m for m in r.plan.meals if m.day < 4]
    assert all(m.locked for m in past) and len(past) == 9
    assert pid not in {i.product_id for m in r.plan.meals if not m.locked for i in m.items}


def test_replan_equipment_lost(planned):
    a, s = planned
    r = a.replan(s, "the microwave is broken", today=2, now=MealSlot.LUNCH)
    assert r.status == "planned"
    for m in r.plan.meals:
        if not m.locked:
            assert all("microwave" not in [e.value for e in BY_ID[i.product_id].requires] for i in m.items)


def test_replan_not_understood(planned):
    a, s = planned
    r = a.replan(s, "blah", today=2, now=MealSlot.LUNCH)
    assert "could not understand" in r.message and r.plan == s.plan


def test_db_persistence():
    conn = init_db(":memory:")
    import_catalog(conn, CSV)
    c = Constraints(weekly_budget_krw=50000)
    save_user(conn, "u1", c)
    assert load_user(conn, "u1") == c
    from dormmeal.models import Meal, MealPlan, PlanItem
    plan = MealPlan(meals=[Meal(day=1, slot=MealSlot.LUNCH, items=[PlanItem(product_id="CU001", quantity=1)])])
    save_plan(conn, "u1", plan, 1400, False)
    assert latest_plan(conn, "u1") == plan
    set_preference(conn, "u1", "CU001", True)
    set_preference(conn, "u1", "CU002", False)
    assert get_preferences(conn, "u1") == (["CU001"], ["CU002"])
    log_event(conn, "u1", "sold out", Event(type="sold_out", product_id="CU001", raw_text="sold out"))
    assert conn.execute("SELECT COUNT(*) FROM event_logs").fetchone()[0] == 1
