"""Week 11 evaluation: from which weekly budget does DormMeal meet every daily target?

Usage: python benchmark/budget_sensitivity.py [time_limit_s]   -> benchmark/SENSITIVITY.md
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dormmeal.models import Constraints  # noqa: E402
from dormmeal.optimizer import optimize  # noqa: E402
from dormmeal.tools import load_catalog_csv  # noqa: E402
from dormmeal.verifier import verify  # noqa: E402

CATALOG = load_catalog_csv(ROOT / "data" / "catalog.csv")
PROFILES = {
    "no equipment": dict(equipment=[]),
    "microwave": dict(equipment=["microwave"]),
    "microwave + fridge": dict(equipment=["microwave", "fridge"]),
    "microwave + fridge, vegetarian": dict(equipment=["microwave", "fridge"], diet="vegetarian"),
    "all equipment, sourced products only": dict(equipment=["microwave", "kettle", "fridge"], sourced_only=True),
}
BUDGETS = [50000, 60000, 70000, 80000, 90000, 100000]


def main(time_limit=8):
    lines = ["# Budget sensitivity (3 meals/day, 7 days)", "",
             f"Optimizer time limit {time_limit} s, catalog.csv (98 sourced + 150 estimated products). Cell = days that miss "
             "a nutrition target (0 = fully valid plan), `-` = no plan.", "",
             "| Profile | " + " | ".join(f"{b // 1000}k" for b in BUDGETS) + " |",
             "|---|" + "---|" * len(BUDGETS)]
    for name, kw in PROFILES.items():
        cells = []
        for b in BUDGETS:
            c = Constraints(weekly_budget_krw=b, **kw)
            r = optimize(CATALOG, c, time_limit_s=time_limit)
            if r.plan is None:
                cells.append("-")
                continue
            res = verify(r.plan, CATALOG, c)
            bad_days = {v.detail.split(":")[0] for v in res.violations if v.rule == "nutrition"}
            cells.append(str(len(bad_days)))
            print(name, b, len(bad_days), res.totals.total_cost_krw, flush=True)
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    (Path(__file__).resolve().parent / "SENSITIVITY.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 8)
