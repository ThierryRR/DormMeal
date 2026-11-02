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


def init_db(path: str | Path = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
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
