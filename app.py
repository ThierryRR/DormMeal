"""DormMeal Streamlit interface.   Run: streamlit run app.py"""
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from dormmeal import llm
from dormmeal.agent import DormMealAgent
from dormmeal.db import (get_preferences, import_catalog, init_db, log_event, save_plan, save_user,
                         set_preference)
from dormmeal.models import Constraints, Diet, Equipment, MealSlot, Store
from dormmeal.parser import ALLERGEN_WORDS
from dormmeal.tools import load_catalog_csv

ROOT = Path(__file__).resolve().parent
CSV = ROOT / "data" / "catalog.csv"
DB = ROOT / "dormmeal.db"
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

st.set_page_config(page_title="DormMeal", page_icon="🍙", layout="wide")

# Streamlit Community Cloud: the key is stored in the app's Secrets, never in the repository
try:
    if "GEMINI_API_KEY" in st.secrets and not os.environ.get("GEMINI_API_KEY"):
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
except Exception:   # no secrets file: run without the LLM
    pass


@st.cache_resource
def get_agent():
    return DormMealAgent(load_catalog_csv(CSV), use_llm=True, time_limit_s=20)


@st.cache_resource
def get_db():
    conn = init_db(DB, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        import_catalog(conn, CSV)
    return conn


agent, conn = get_agent(), get_db()
ss = st.session_state

# ---------------- sidebar: who and how ----------------
st.sidebar.title("🍙 DormMeal")
st.sidebar.caption("Weekly convenience-store meal plans for students in Korean dorms.")
user_id = st.sidebar.text_input("Your nickname (to remember likes)", value="guest")
liked, disliked = get_preferences(conn, user_id)
mode = st.sidebar.radio("How do you want to describe your week?", ["Form", "In my own words"])
st.sidebar.caption("Free-text understanding: " + ("Gemini + rules" if llm.available() else "rules only (no API key)"))

st.title("Plan my week")
n_src = sum(p.verified for p in agent.catalog)
st.info(f"Catalog: {n_src} products with sourced data (MFDS / manufacturer / Meokfit, reference prices) and "
        f"{len(agent.catalog) - n_src} **estimated** products. Allergen information is missing for sourced products: "
        "they are never proposed to users who declare an allergy.", icon="ℹ️")
sourced_only = st.checkbox("Use only products with sourced data (fewer choices, less protein)", value=False)

constraints, text = None, ""
if mode == "Form":
    c1, c2, c3 = st.columns(3)
    budget = c1.number_input("Weekly budget (KRW)", min_value=10000, max_value=300000, value=70000, step=5000)
    meals = c1.selectbox("Meals per day", [3, 2, 1], help="2 = lunch and dinner, 1 = lunch")
    equipment = c2.multiselect("Equipment I can use", [e.value for e in Equipment], default=["microwave"])
    diet = c2.selectbox("Diet", [d.value for d in Diet], help="halal_friendly: no product is certified yet")
    allergies = c3.multiselect("Allergies / foods I can't eat", sorted(ALLERGEN_WORDS))
    stores = c3.multiselect("Stores I can reach", [s.value for s in Store], default=[s.value for s in Store])
    constraints = Constraints(weekly_budget_krw=int(budget), meals_per_day=meals, equipment=equipment, diet=diet,
                              allergies=allergies, stores=stores or [s.value for s in Store],
                              liked_product_ids=liked, disliked_product_ids=disliked, sourced_only=sourced_only)
else:
    text = st.text_area("Describe your situation", height=90,
                        placeholder="e.g. I have 60,000 won for the week, a microwave and a fridge, "
                                    "I'm vegetarian and allergic to nuts. I skip breakfast.")

if st.button("Plan my week", type="primary"):
    with st.spinner("Building and checking your plan (up to 20 s)..."):
        if constraints is None:
            s = agent.plan(text)
            if s.constraints is not None:   # add stored preferences, then solve again
                c = s.constraints.model_copy(update={"liked_product_ids": liked, "disliked_product_ids": disliked,
                                                     "sourced_only": sourced_only})
                s = agent.plan(constraints=c) if (liked or disliked or sourced_only) else s
                s.request = text
        else:
            s = agent.plan(constraints=constraints)
    ss["state"] = s
    if s.constraints is not None:
        save_user(conn, user_id, s.constraints)
    if s.plan is not None:
        save_plan(conn, user_id, s.plan, s.verification.totals.total_cost_krw, s.verification.valid)


def show_state(s):
    if s.status in ("need_info", "infeasible", "error"):
        (st.info if s.status == "need_info" else st.error)(s.message)
        return
    tot, c = s.verification.totals, s.constraints
    days = [d for d in range(1, 8) if any(m.day == d and m.items for m in s.plan.meals)]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total cost", f"{tot.total_cost_krw:,} KRW", f"{c.weekly_budget_krw - tot.total_cost_krw:,} left")
    m2.metric("Avg kcal / day", f"{sum(tot.daily_kcal.get(d, 0) for d in days) / len(days):.0f}")
    m3.metric("Avg protein / day", f"{sum(tot.daily_protein_g.get(d, 0) for d in days) / len(days):.0f} g")
    m4.metric("Avg sodium / day", f"{sum(tot.daily_sodium_mg.get(d, 0) for d in days) / len(days):.0f} mg")
    st.text(s.message)

    tab1, tab2, tab3, tab4 = st.tabs(["📅 Week", "🛒 Shopping list", "📊 Nutrition", "🔎 Checks"])
    with tab1:
        rows = agent.meal_rows(s.plan)
        df = pd.DataFrame(rows)
        df["day"] = df["day"].map(lambda d: DAY_NAMES[d - 1])
        grid = df.pivot(index="slot", columns="day", values="items").reindex(
            [x.value for x in MealSlot if x.value in df["slot"].values])[[d for d in DAY_NAMES if d in df["day"].values]]
        st.dataframe(grid, use_container_width=True)
        st.caption("🔒 = already eaten (kept when replanning)" if any(r["locked"] for r in rows) else "")
    with tab2:
        shop = pd.DataFrame(agent.shopping_list(s.plan))
        shop["data"] = shop["product_id"].map(lambda p: "sourced" if agent.by_id[p].verified else "estimate")
        st.caption(f"{(shop['data'] == 'sourced').sum()} of {len(shop)} products have sourced data.")
        for store, part in shop.groupby("store"):
            st.subheader(f"{store}: {part['cost_krw'].sum():,} KRW")
            st.dataframe(part[["product", "units", "paid_units", "promo", "unit_price_krw", "cost_krw", "where", "prep",
                               "data"]],
                         hide_index=True, use_container_width=True)
    with tab3:
        t = c.targets
        nut = pd.DataFrame({"kcal": [tot.daily_kcal.get(d, 0) for d in range(1, 8)],
                            "protein_g": [tot.daily_protein_g.get(d, 0) for d in range(1, 8)],
                            "sodium_mg": [tot.daily_sodium_mg.get(d, 0) for d in range(1, 8)]}, index=DAY_NAMES)
        st.caption(f"Targets for 3 meals: {t.kcal_per_day[0]:.0f}-{t.kcal_per_day[1]:.0f} kcal, "
                   f">= {t.protein_g_per_day_min:.0f} g protein, <= {t.sodium_mg_per_day_max:.0f} mg sodium "
                   "(scaled down on days with fewer meals).")
        st.bar_chart(nut[["kcal"]])
        st.bar_chart(nut[["protein_g"]])
        st.bar_chart(nut[["sodium_mg"]])
    with tab4:
        if s.verification.violations:
            for v in s.verification.violations:
                st.write(f"• **{v.rule}**: {v.detail}")
        else:
            st.success("All checks passed: budget, allergens, equipment, diet, stores, variety, nutrition.")
        with st.expander("Agent trace"):
            st.code("\n".join(s.trace))

    st.divider()
    st.subheader("Something changed this week?")
    c1, c2, c3 = st.columns([1, 1, 3])
    today = c1.selectbox("Today", list(range(1, 8)), format_func=lambda d: DAY_NAMES[d - 1])
    now = c2.selectbox("Next meal", [x.value for x in MealSlot], index=1)
    ev_text = c3.text_input("What happened?", placeholder="The tuna kimbap was sold out at GS25 / "
                                                           "I'll skip dinner on Friday / my microwave is broken")
    if st.button("Update my plan") and ev_text:
        with st.spinner("Replanning the rest of the week..."):
            new = agent.replan(s, ev_text, today=today, now=MealSlot(now))
        log_event(conn, user_id, ev_text)
        ss["state"] = new
        if new.plan is not None:
            save_plan(conn, user_id, new.plan, new.verification.totals.total_cost_krw, new.verification.valid)
        st.rerun()

    st.subheader("Like or reject a product")
    used = sorted({i.product_id for m in s.plan.meals for i in m.items})
    pick = st.selectbox("Product", used, format_func=lambda p: f"{agent.by_id[p].name_en} ({agent.by_id[p].store.value})")
    b1, b2, _ = st.columns([1, 1, 4])
    if b1.button("👍 Like"):
        set_preference(conn, user_id, pick, True)
        st.toast("Saved: liked products are preferred in the next plan.")
    if b2.button("👎 Never again"):
        set_preference(conn, user_id, pick, False)
        st.toast("Saved: this product will be excluded from your next plan.")


if "state" in ss:
    show_state(ss["state"])
