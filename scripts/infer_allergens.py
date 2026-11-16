"""Infer allergens of SOURCED products from their Korean / English product name.

The workbook has no ingredient list ("Non disponible"), so this is a keyword rule, NOT the package label.
Rules:
- only rows without allergen data are changed;
- the inferred list is written in the allergens column for information, with a source note;
- allergens_known stays false: the list is INCOMPLETE (e.g. bibimbap often contains egg, fried coatings
  often contain wheat), so a product is still excluded for users who declare an allergy.
Users must still check the package label. Run after scripts/import_excel.py.

Usage: python scripts/infer_allergens.py
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES = {
    "milk": ["우유", "치즈", "요구르트", "요거트", "라떼", "밀크", "버터", "아이스크림", "빙수", "milk", "cheese",
             "latte", "yogurt", "yoghurt", "butter", "bingsu", "ice cream", "cream", "lactose"],
    "egg": ["계란", "달걀", "에그", "마요", "egg", "mayo", "omurice", "오므라이스"],
    "wheat": ["라면", "우동", "국수", "면", "빵", "밀가루", "만두", "샌드", "버거", "크림빵", "짬뽕", "짜장",
              "noodle", "ramen", "bread", "burger", "sandwich", "udon", "ramyun", "bun", "sesame ramen"],
    "soy": ["두부", "두유", "콩", "간장", "된장", "고추장", "베지밀", "쌈장", "tofu", "soy", "soya", "soybean",
            "miso", "gochujang"],
    "fish": ["참치", "고등어", "멸치", "어묵", "생선", "연어", "맛살", "액젓", "tuna", "salmon", "anchovy", "fish",
             "mackerel", "fish cake"],
    "crustacean": ["새우", "게맛살", "크래미", "shrimp", "crab", "kraemi"],
    "pork": ["돼지", "돈까스", "돈", "햄", "베이컨", "스팸", "삼겹", "제육", "탕수육", "pork", "ham", "bacon", "spam"],
    "beef": ["소고기", "쇠고기", "소불고기", "불고기", "사골", "beef", "bulgogi"],
    "chicken": ["닭", "치킨", "가라아게", "chicken", "karaage"],
    "nuts": ["땅콩", "아몬드", "호두", "견과", "캐슈", "nuts", "almond", "peanut", "walnut"],
}


def infer(name: str) -> list[str]:
    text = name.lower()
    found = []
    for allergen, words in RULES.items():
        if any(w.lower() in text for w in words):
            found.append(allergen)
    return found


def process(path: Path) -> tuple[int, int]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fields = list(rows[0].keys())
    changed = total = 0
    for r in rows:
        if not r.get("name_ko") or r.get("allergens_known", "true").lower() == "true" or r.get("allergens"):
            continue
        total += 1
        found = infer(r["name_ko"])   # Korean label only: English names gave false positives (e.g. "fish ice cream")
        if found:
            r["allergens"] = ";".join(found)   # informational only, allergens_known stays false
            r["source"] = (r["source"] + " | allergens inferred from Korean name (keyword rule, "
                           "incomplete), not from the label; allergens_known=false").strip(" |")
            changed += 1
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows(rows)
    return changed, total


if __name__ == "__main__":
    for name in ["catalog_sourced.csv", "catalog.csv"]:
        p = ROOT / "data" / name
        c, t = process(p)
        print(f"{name}: allergens inferred for {c} of {t} sourced products without allergen data")
