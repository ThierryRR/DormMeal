"""Print a quality / progress report of a catalog CSV.   Usage: python scripts/validate_catalog.py [csv]
Exit code 1 if blocking issues are found (useful in CI)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dormmeal.tools import load_catalog_csv  # noqa: E402
from dormmeal.validation import catalog_report  # noqa: E402

path = sys.argv[1] if len(sys.argv) > 1 else "data/catalog_v1.csv"
r = catalog_report(load_catalog_csv(path))
print(f"Products : {r['total']} / {r['target']} target ({r['progress_pct']}%)")
print(f"Verified : {r['verified']} ({r['verified_pct']}%)")
print(f"Per store: {r['per_store']}")
print(f"Promos   : {r['with_promo']} products")
print(f"Categories: {r['per_category']}")
if r["issues"]:
    print(f"\n{len(r['issues'])} issue(s):")
    for i in r["issues"]:
        print("  -", i)
    sys.exit(1)
print("\nNo issues found.")
