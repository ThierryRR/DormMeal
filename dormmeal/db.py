"""SQLite schema and catalog import."""
import json
import sqlite3
from pathlib import Path

from .models import Product
from .tools import load_catalog_csv

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    name_en TEXT NOT NULL,
    store TEXT NOT NULL,
    category TEXT NOT NULL,
    price_krw INTEGER NOT NULL CHECK (price_krw >= 0),
    promo_type TEXT NOT NULL DEFAULT 'none',
    kcal REAL, protein_g REAL, carbs_g REAL, fat_g REAL, sodium_mg REAL,
    allergens TEXT NOT NULL DEFAULT '[]',      -- JSON list
    diet_tags TEXT NOT NULL DEFAULT '[]',      -- JSON list
    requires TEXT NOT NULL DEFAULT '[]',       -- JSON list
    prep_instructions TEXT,
    description TEXT NOT NULL,
    last_updated TEXT NOT NULL,
    verified INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    constraints_json TEXT NOT NULL,            -- serialized Constraints
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS plans (
    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    plan_json TEXT NOT NULL,                   -- serialized MealPlan
    total_cost_krw INTEGER,
    valid INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS preferences (
    user_id TEXT NOT NULL REFERENCES users(user_id),
    product_id TEXT NOT NULL REFERENCES products(product_id),
    liked INTEGER NOT NULL,                    -- 1 liked, 0 rejected
    PRIMARY KEY (user_id, product_id)
);
CREATE TABLE IF NOT EXISTS event_logs (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    event_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db(path: str | Path = ":memory:", check_same_thread: bool = True) -> sqlite3.Connection:
    """`check_same_thread=False` is needed by Streamlit, which runs each rerun in another thread."""
    conn = sqlite3.connect(str(path), check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def import_catalog(conn: sqlite3.Connection, csv_path: str | Path) -> int:
    products = load_catalog_csv(csv_path)
    conn.executemany(
        """INSERT OR REPLACE INTO products
           (product_id, name_en, store, category, price_krw, promo_type, kcal, protein_g, carbs_g,
            fat_g, sodium_mg, allergens, diet_tags, requires, prep_instructions, description,
            last_updated, verified, source)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [(p.product_id, p.name_en, p.store.value, p.category, p.price_krw, p.promo_type.value,
          p.kcal, p.protein_g, p.carbs_g, p.fat_g, p.sodium_mg,
          json.dumps(p.allergens), json.dumps([d.value for d in p.diet_tags]),
          json.dumps([e.value for e in p.requires]), p.prep_instructions, p.description,
          p.last_updated, int(p.verified), p.source) for p in products])
    conn.commit()
    return len(products)


def fetch_catalog(conn: sqlite3.Connection) -> list[Product]:
    out = []
    for r in conn.execute("SELECT * FROM products ORDER BY product_id"):
        d = dict(r)
        for k in ("allergens", "diet_tags", "requires"):
            d[k] = json.loads(d[k])
        d["verified"] = bool(d["verified"])
        out.append(Product(**d))
    return out


# ---------------- users, plans, preferences, events (week 5) ----------------
def save_user(conn: sqlite3.Connection, user_id: str, constraints) -> None:
    conn.execute("INSERT OR REPLACE INTO users (user_id, constraints_json) VALUES (?, ?)",
                 (user_id, constraints.model_dump_json()))
    conn.commit()


def load_user(conn: sqlite3.Connection, user_id: str):
    from .models import Constraints
    row = conn.execute("SELECT constraints_json FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return Constraints.model_validate_json(row["constraints_json"]) if row else None


def save_plan(conn: sqlite3.Connection, user_id: str, plan, total_cost_krw: int, valid: bool) -> int:
    cur = conn.execute("INSERT INTO plans (user_id, plan_json, total_cost_krw, valid) VALUES (?, ?, ?, ?)",
                       (user_id, plan.model_dump_json(), total_cost_krw, int(valid)))
    conn.commit()
    return cur.lastrowid


def latest_plan(conn: sqlite3.Connection, user_id: str):
    from .models import MealPlan
    row = conn.execute("SELECT plan_json FROM plans WHERE user_id = ? ORDER BY plan_id DESC LIMIT 1",
                       (user_id,)).fetchone()
    return MealPlan.model_validate_json(row["plan_json"]) if row else None


def set_preference(conn: sqlite3.Connection, user_id: str, product_id: str, liked: bool) -> None:
    conn.execute("INSERT OR REPLACE INTO preferences (user_id, product_id, liked) VALUES (?, ?, ?)",
                 (user_id, product_id, int(liked)))
    conn.commit()


def get_preferences(conn: sqlite3.Connection, user_id: str) -> tuple[list[str], list[str]]:
    rows = conn.execute("SELECT product_id, liked FROM preferences WHERE user_id = ? ORDER BY product_id",
                        (user_id,)).fetchall()
    return [r["product_id"] for r in rows if r["liked"]], [r["product_id"] for r in rows if not r["liked"]]


def log_event(conn: sqlite3.Connection, user_id: str, raw_text: str, event=None) -> None:
    conn.execute("INSERT INTO event_logs (user_id, raw_text, event_json) VALUES (?, ?, ?)",
                 (user_id, raw_text, event.model_dump_json() if event is not None else None))
    conn.commit()
