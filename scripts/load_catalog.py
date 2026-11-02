"""Create dormmeal.db and import data/catalog_v1.csv.   Usage: python scripts/load_catalog.py [csv] [db]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dormmeal.db import import_catalog, init_db  # noqa: E402

csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/catalog_v1.csv"
db_path = sys.argv[2] if len(sys.argv) > 2 else "dormmeal.db"
conn = init_db(db_path)
print(f"Imported {import_catalog(conn, csv_path)} products into {db_path}")
