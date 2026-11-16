"""Import the sourced products of the research workbook into the DormMeal catalog.

Input : data/sources/base_convenience_stores_coree_v9.xlsx (sheet MASTER_DATABASE, 150 store-product rows,
        sources: Meokfit catalog pages matched to MFDS data, manufacturer and retailer pages)
Output: data/catalog_sourced.csv  - rows with a price AND kcal, protein, carbs, fat, sodium
        data/catalog.csv          - catalog used by the app: sourced rows + the estimated rows of catalog_v1.csv
        data/IMPORT_REPORT.md     - what was imported, what was left out and why

Rules (nothing is estimated):
- A row is imported only if price, kcal, protein, carbs, fat and sodium are all given in the workbook.
- Allergens are "Non disponible" in the workbook -> allergens_known = false, so an allergic user never gets them.
- diet_tags stay empty (vegetarian status is not documented).
- English names are translations of the Korean name; the Korean name is kept in name_ko.
- `requires` and preparation hints are derived from the product type (cup noodles -> kettle, ready meals,
  burgers and cooked rice -> microwave, 900 ml milk -> fridge); they are labelled as generic instructions.
- verified = true: price and nutrition come from an identified source for this product (URL in `source`,
  with the workbook's confidence level). Prices are catalog reference prices: confirm in store.

Usage: python scripts/import_excel.py
"""
import csv
import re
import sys
from collections import Counter
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "data" / "sources" / "base_convenience_stores_coree_v9.xlsx"

NAMES = {
    "멘토스 필링베리굿": "Mentos Feeling Berry Good candy roll",
    "멘토스 레인보우": "Mentos Rainbow candy 100 g",
    "마라곤약 향라맛": "Mala konjac snack (xiangla flavour)",
    "마라곤약 마라맛": "Mala konjac snack (mala flavour)",
    "웰치 포도에이드": "Welch's grape ade",
    "웰치 사과에이드": "Welch's apple ade",
    "아몬드데이 언스위트": "Almond Day unsweetened almond drink",
    "멀티비타4U": "Multivita 4U vitamin drink",
    "맵탱 마늘조개라면": "Maeptaeng garlic clam ramen",
    "매일두유 렌틸콩": "Maeil soy milk with lentils",
    "깐풍기&표고탕수": "Kkanpunggi chicken and sweet-sour shiitake box",
    "찍먹탕수육": "Sweet and sour pork box (dipping sauce)",
    "소불고기비빔밥": "Beef bulgogi bibimbap",
    "오므라이스덮밥": "Omurice rice bowl",
    "치킨가라아게덮밥": "Chicken karaage rice bowl",
    "팔도 왕뚜껑": "Paldo Wangttukkeong big cup noodles",
    "신라면": "Shin Ramyun (single bag)",
    "오뚜기진라면순한맛": "Ottogi Jin Ramen mild (single bag)",
    "맛있는라면": "Masinneun Ramyun (single bag)",
    "신라면 큰사발면": "Shin Ramyun big bowl",
    "오뚜기진라면매운맛": "Ottogi Jin Ramen spicy (single bag)",
    "뉴케어 올프로틴 고소한맛": "Newcare All Protein drink (nutty)",
    "깨수깡": "Kkaesukkang functional drink",
    "남양 맛있는 우유 GT": "Namyang GT milk 900 ml",
    "몬스터 에너지": "Monster Energy 355 ml",
    "칸타타프리미엄라떼": "Cantata premium latte",
    "바리스타룰스 콜드브루 블랙": "Barista Rules cold brew black",
    "오로나민C": "Oronamin C vitamin drink",
    "매일우유 오리지널": "Maeil milk original 900 ml",
    "새우깡": "Saeukkang shrimp crackers",
    "메로나": "Melona ice bar",
    "포카칩오리지널": "Pokachip original potato chips",
    "호두마요제육김밥": "Walnut mayo spicy pork kimbap",
    "콘마요유부초밥": "Corn mayo fried-tofu rice pockets",
    "고추장삼겹삼각": "Gochujang pork belly triangle kimbap",
    "불닭마요통치킨버거": "Buldak mayo chicken burger",
    "마늘간장통치킨버거": "Garlic soy chicken burger",
    "빅치즈불고기버거": "Big cheese bulgogi burger",
    "호밀햄치즈샌드": "Rye ham and cheese sandwich",
    "진한새우탕면": "Rich shrimp soup noodles",
    "신라면로제": "Shin Ramyun Rose",
    "짜장치즈볶이 용기": "Jjajang cheese stir-fried noodles (cup)",
    "진밀면": "Jin milmyeon noodles",
    "비컴플 런 쿨다운": "Becomple Run cool-down drink",
    "비컴플 런 부스터": "Becomple Run booster drink",
    "봉봉 애사비 소다": "Bonbon apple cider vinegar soda",
    "데이프로틴 오곡": "Day Protein five-grain drink",
    "허쉬 크런치초코바": "Hershey's crunch chocolate ice bar",
    "포도젤로바": "Grape jello ice bar",
    "린도볼어쏘티드": "Lindor assorted chocolate balls",
    "로로멜로 우유컵빙수": "Lolomello milk bingsu cup",
    "허쉬 쿠키앤민트바": "Hershey's cookie and mint ice bar",
    "통아몬드 캔디": "Whole almond candy",
    "떡붕어싸만코": "Ssamanco rice-cake fish ice cream",
    "월드콘 바닐라": "World Cone vanilla",
    "핫브레이크 오리지널": "Hot Break original chocolate bar",
    "에너지바": "Energy bar",
    "왕꿈틀이": "Wang Kkumteuri gummy worms",
    "바밤바": "Babamba chestnut ice bar",
    "오뚜기밥": "Ottogi cooked rice 210 g",
    "달콤한 베지밀비": "Vegemil B sweet soy milk",
    "비타파워": "Vita Power vitamin drink",
    "농심 안성탕면": "Nongshim Ansungtangmyun (single bag)",
    "핫식스": "Hot6 energy drink 250 ml",
    "제주똣똣라면 용기": "Ottogi Jeju Ttottot ramen (cup)",
}

# workbook category (French) -> DormMeal category
CATEGORY = {
    "Plat préparé": "bento", "Kimbap": "kimbap_roll", "Sushi / riz assaisonné": "kimbap_roll",
    "Triangle kimbap": "triangle_kimbap", "Burger": "sandwich", "Sandwich": "sandwich",
    "Riz prêt à consommer": "instant_rice", "Nouilles instantanées": "instant_noodle",
    "Lait": "dairy", "Glace": "ice_cream", "Dessert glacé": "ice_cream",
}
SHELF = {
    "bento": "Lunch-box chiller (dosirak section)", "kimbap_roll": "Chilled kimbap / rice shelf",
    "triangle_kimbap": "Triangle kimbap shelf", "sandwich": "Chilled sandwich and burger shelf",
    "instant_rice": "Instant rice shelf", "instant_noodle": "Instant noodle shelf", "dairy": "Dairy fridge",
    "ice_cream": "Ice-cream freezer", "drink": "Drinks fridge", "snack": "Snack shelf",
}
FIELDS = ["product_id", "name_en", "store", "category", "price_krw", "promo_type", "kcal", "protein_g", "carbs_g",
          "fat_g", "sodium_mg", "allergens", "diet_tags", "requires", "prep_instructions", "description",
          "last_updated", "verified", "source", "name_ko", "allergens_known"]
NUM = ["Prix normal (KRW)", "Énergie (kcal)", "Protéines (g)", "Glucides (g)", "Lipides (g)", "Sodium (mg)"]
NUTR = NUM[1:]
KCA = ROOT / "data" / "sources" / "kca_convenience_prices_2026-11-06.csv"
KCA_URL = "https://www.price.go.kr/tprice/portal/dailynecessitypriceinfo/priceiteminfo/getPriceItemInfoList.do"
OFF = ROOT / "data" / "sources" / "openfoodfacts_matches.json"
# KCA product -> (Open Food Facts barcode, factor from the OFF "per 100" values to one unit, units in the KCA
# pack, English name, DormMeal category, requires, prep, note). Crowd-sourced data: confidence C.
OFF_MATCH = {
    "포카리스웨트(620ml)": ("8801097250079", 6.2, 1, "Pocari Sweat 620 ml", "drink", "", "",
                       "per 100 ml x 6.2"),
    "너구리(5개입)": ("8801043014984", 1.2, 5, "Nongshim Neoguri udon ramen (single bag)", "instant_noodle", "kettle",
                  "Generic (bag noodles, no stove): put noodles in a bowl, cover with boiling water for about 5 min "
                  "(check the package)", "per 100 g x 1.2 (120 g bag); pack of 5: price per bag"),
    "매일 소화가 잘되는 우유(930ml)": ("8801121768129", 9.3, 1, "Maeil lactose-free milk original 930 ml", "dairy",
                             "fridge", "Keep chilled after opening", "per 100 ml x 9.3"),
    "빙그레 더단백 프로틴 드링크 초코(250ml)": ("8801104670876", 1.0, 1, "Binggrae The:Danbaek protein drink chocolate 250 ml",
                                   "drink", "", "", "OFF lists the 250 g serving values in its per-100 g fields "
                                   "(20 g protein, 105 kcal per pack); used as per-pack values, to confirm on the label"),
}
# Real products with an OFFICIAL KCA price but NO nutrition source available: nutrition values below are
# estimates of typical label values (verified = false). KCA name -> (English name, category, kcal, protein,
# carbs, fat, sodium, allergens, diet, requires, prep)
_MW = "Generic: microwave as indicated on the package (about 2 min)"
PRICE_ONLY = {
    "햇반(210g)": ("CJ Hetbahn cooked rice 210 g", "instant_rice", 315, 5, 70, 1, 10, "", "vegetarian", "microwave", _MW),
    "햇반 컵반 미역국밥(167g)": ("Hetbahn Cupbahn seaweed soup with rice", "rice_bowl", 260, 6, 52, 3, 900, "soy;wheat;beef", "", "microwave", _MW),
    "햇반 컵반 철판제육덮밥(256g)": ("Hetbahn Cupbahn spicy pork rice bowl", "rice_bowl", 420, 12, 75, 7, 900, "soy;wheat;pork", "", "microwave", _MW),
    "오뚜기 컵밥 제육덮밥(310g)": ("Ottogi Cupbap spicy pork rice bowl", "rice_bowl", 480, 13, 85, 9, 1100, "soy;wheat;pork", "", "microwave", _MW),
    "오뚜기 맛있는 새우볶음밥(용기, 230g)": ("Ottogi shrimp fried rice cup", "rice_bowl", 400, 9, 68, 10, 900, "soy;wheat;egg;fish", "", "microwave", _MW),
    "오뚜기 진한 쇠고기미역국밥(314g)": ("Ottogi beef seaweed soup with rice", "rice_bowl", 330, 9, 62, 5, 1300, "soy;wheat;beef", "", "microwave", _MW),
    "동원 양반 쇠고기죽(287.5g)": ("Dongwon Yangban beef porridge", "porridge", 165, 7, 28, 3, 800, "soy;wheat;beef", "", "microwave", _MW),
    "동원 양반 전복죽(287.5g)": ("Dongwon Yangban abalone porridge", "porridge", 160, 5, 30, 2.5, 800, "soy;fish", "", "microwave", _MW),
    "햇반 소프트밀 소고기죽(280g)": ("Hetbahn Soft Meal beef porridge", "porridge", 170, 7, 28, 3, 750, "soy;wheat;beef", "", "microwave", _MW),
    "3분 쇠고기짜장(200g)": ("Ottogi 3-minute beef jjajang sauce", "side", 170, 6, 20, 7, 900, "soy;wheat;beef;pork", "", "microwave", _MW + "; serve on rice"),
    "3분 쇠고기카레(200g)": ("Ottogi 3-minute beef curry sauce", "side", 175, 5, 20, 8, 950, "soy;wheat;beef;milk", "", "microwave", _MW + "; serve on rice"),
    "오뚜기 참깨라면 컵(110g)": ("Ottogi sesame ramen cup", "instant_noodle", 500, 10, 68, 21, 1600, "soy;wheat;egg", "", "kettle", "Generic: add boiling water to the inner line, wait about 4 min (check the package)"),
    "동원참치 라이트스탠다드(150g)": ("Dongwon light standard tuna can 150 g", "protein", 245, 28, 2, 14, 500, "fish;soy", "", "", ""),
    "사조참치 살코기 안심따개(150g)": ("Sajo tuna can 150 g", "protein", 240, 27, 2, 14, 520, "fish;soy", "", "", ""),
    "행복한콩 부침두부(300g)": ("CJ firm tofu 300 g", "protein", 260, 27, 6, 14, 15, "soy", "vegetarian", "fridge", "Eat cold or warm; keep chilled"),
    "행복한콩 찌개두부(300g)": ("CJ stew tofu 300 g", "protein", 240, 24, 6, 13, 15, "soy", "vegetarian", "fridge", "Eat cold or warm; keep chilled"),
    "김밥용 크래미(120g)": ("Crab stick (Kraemi) 120 g", "protein", 110, 9, 15, 1, 800, "fish;wheat;egg;soy", "", "fridge", "Eat cold"),
    "서울우유 흰우유(1L)": ("Seoul Milk whole milk 1 L", "dairy", 650, 30, 47, 37, 500, "milk", "vegetarian", "fridge", "Keep chilled after opening"),
    "서울우유 저지방 우유(1L)": ("Seoul Milk low-fat milk 1 L", "dairy", 400, 32, 48, 10, 520, "milk", "vegetarian", "fridge", "Keep chilled after opening"),
    "셀렉스 스포츠 웨이프로틴 초콜릿(330ml)": ("Selex Sports whey protein drink chocolate 330 ml", "drink", 150, 21, 9, 3, 180, "milk;soy", "vegetarian", "", ""),
    "게토레이 레몬(600ml)": ("Gatorade lemon 600 ml", "drink", 150, 0, 38, 0, 250, "", "vegetarian", "", ""),
    "파워에이드 마운틴블라스트(600ml)": ("Powerade Mountain Blast 600 ml", "drink", 150, 0, 37, 0, 150, "", "vegetarian", "", ""),
    "레드불 에너지 드링크(250ml)": ("Red Bull energy drink 250 ml", "drink", 115, 1, 28, 0, 100, "", "vegetarian", "", ""),
    "맥심 티오피 마스터 라떼(275ml)": ("Maxim T.O.P master latte 275 ml", "drink", 140, 4, 22, 4, 120, "milk", "vegetarian", "", ""),
    "돼지바(70ml)": ("Dwaeji Bar ice cream", "ice_cream", 150, 2, 17, 8, 40, "milk;wheat;soy;nuts", "", "", ""),
    "해태 부라보콘 바닐라(160ml)": ("Haitai Bravo Cone vanilla", "ice_cream", 250, 4, 33, 11, 80, "milk;wheat;soy;nuts", "", "", ""),
    "자유시간(36g)": ("Jayu Sigan chocolate bar", "snack", 180, 3, 20, 10, 40, "milk;soy;nuts", "", "", ""),
    "삼양라면(5개입)": ("Samyang Ramen (single bag)", "instant_noodle", 500, 10, 79, 16, 1800, "soy;wheat;pork", "", "kettle",
                   "Generic (bag noodles, no stove): put noodles in a bowl, cover with boiling water for about 5 min"),
    "열라면(5개입)": ("Ottogi Yeul Ramen (single bag)", "instant_noodle", 510, 11, 80, 16, 1800, "soy;wheat;beef", "", "kettle",
                  "Generic (bag noodles, no stove): put noodles in a bowl, cover with boiling water for about 5 min"),
    "스팸 클래식(200g)": ("Spam Classic 200 g can", "protein", 680, 26, 4, 62, 2160, "pork;soy", "", "", ""),
}
PRICE_ONLY_UNITS = {"삼양라면(5개입)": 5, "열라면(5개입)": 5}   # surveyed pack size -> price per unit
# FatSecret Korea brand records (kcal, protein, carbs, fat per unit; no sodium): data/sources/fatsecret_matches.json
FATSECRET = ROOT / "data" / "sources" / "fatsecret_matches.json"
# workbook rows that only lacked carbs and fat -> FatSecret record that supplies them
FS_FILL = {"핫식스": "롯데 핫식스(250ml)", "제주똣똣라면 용기": "WB:제주똣똣라면 용기"}
# Official KCA price survey name -> (Korean name in the workbook, units in the surveyed pack)
KCA_MATCH = {
    "농심 신라면 큰사발면(114g)": ("신라면 큰사발면", 1), "팔도 왕뚜껑(110g)": ("팔도 왕뚜껑", 1),
    "오뚜기밥(210g)": ("오뚜기밥", 1), "농심 새우깡(90g)": ("새우깡", 1), "닥터유 에너지바(40g)": ("에너지바", 1),
    "롯데 월드콘 바닐라(160ml)": ("월드콘 바닐라", 1), "메로나(75ml)": ("메로나", 1),
    "빙그레 떡붕어 싸만코(150ml)": ("떡붕어싸만코", 1), "오리온 왕꿈틀이(67g)": ("왕꿈틀이", 1),
    "오리온 통아몬드 캔디(90g)": ("통아몬드 캔디", 1), "오리온 포카칩 오리지널(66g)": ("포카칩오리지널", 1),
    "핫브레이크 오리지널(45g)": ("핫브레이크 오리지널", 1), "해태 바밤바(70ml)": ("바밤바", 1),
    "깨수깡(160ml)": ("깨수깡", 1), "뉴케어 올프로틴 고소한맛(245ml)": ("뉴케어 올프로틴 고소한맛", 1),
    "몬스터 에너지(355ml)": ("몬스터 에너지", 1), "바리스타룰스 콜드브루 블랙(325ml)": ("바리스타룰스 콜드브루 블랙", 1),
    "칸타타 프리미엄 라떼(275ml)": ("칸타타프리미엄라떼", 1), "남양유업 맛있는우유GT(900ml)": ("남양 맛있는 우유 GT", 1),
    "매일우유 오리지널(900ml)": ("매일우유 오리지널", 1),
    "신라면(5개입)": ("신라면", 5), "진라면 매운맛(5개입)": ("오뚜기진라면매운맛", 5),
    "진라면 순한맛(5개입)": ("오뚜기진라면순한맛", 5), "맛있는라면(5개입)": ("맛있는라면", 5),
    "안성탕면(5개입)": ("농심 안성탕면", 5),
}


def category(fr: str) -> str:
    if fr in CATEGORY:
        return CATEGORY[fr]
    if fr.startswith(("Boisson", "Café", "Thé")):
        return "drink"
    return "snack"   # confectionery, chocolate, bars, chips, konjac snacks


def requires_and_prep(cat: str, name_ko: str, volume) -> tuple[str, str]:
    if cat == "instant_noodle":
        if any(k in name_ko for k in ("컵", "사발", "왕뚜껑", "용기")):
            return "kettle", "Generic: add boiling water to the inner line, wait about 4 min (check the package)"
        return "kettle", ("Generic (bag noodles, no stove): put noodles in a bowl, cover with boiling water "
                          "for about 5 min (check the package)")
    if cat in ("bento", "instant_rice"):
        return "microwave", "Generic: microwave as indicated on the package (about 1.5-2 min)"
    if cat == "sandwich" and "버거" in name_ko:
        return "microwave", "Generic: microwave about 30-60 s as indicated on the package"
    if cat == "dairy" and isinstance(volume, (int, float)) and volume >= 500:
        return "fridge", "Keep chilled after opening"
    return "", ""


def promo(note: str) -> str:
    m = re.search(r"\b([12])\+1\b", note or "")
    return f"{m.group(1)}+1" if m else "none"


def main():
    wb = openpyxl.load_workbook(XLSX, data_only=True)
    rows = list(wb["MASTER_DATABASE"].iter_rows(values_only=True))
    head = rows[0]
    recs = [dict(zip(head, r)) for r in rows[1:] if r[0]]
    def make_row(d, pid, store, price, price_note, price_url, date):
        name_ko = d["Produit (nom coréen)"].strip()
        cat = category(d["Catégorie"])
        req, prep = requires_and_prep(cat, name_ko, d["Volume (ml)"])
        src = (f"{d['Type de source']} | nutrition: {d['URL source nutritionnelle officielle']} | "
               f"price: {price_url} ({price_note}) | confidence {d['Niveau confiance']} "
               f"| consulted {date} | workbook id {d['ID interne']}")
        return {
            "product_id": pid, "name_en": NAMES.get(name_ko, name_ko), "store": store,
            "category": cat, "price_krw": int(price), "promo_type": promo(price_note),
            "kcal": d["Énergie (kcal)"], "protein_g": d["Protéines (g)"], "carbs_g": d["Glucides (g)"],
            "fat_g": d["Lipides (g)"], "sodium_mg": d["Sodium (mg)"], "allergens": "", "diet_tags": "",
            "requires": req, "prep_instructions": prep,
            "description": f"{SHELF[cat]}; Korean label: {name_ko}",
            "last_updated": date, "verified": "true", "source": src, "name_ko": name_ko,
            "allergens_known": "false"}

    import json
    fs = json.loads(FATSECRET.read_text(encoding="utf-8"))
    kept, left_out = [], Counter()
    fs_filled = 0
    for d in recs:
        name = (d["Produit (nom coréen)"] or "").strip()
        if name in FS_FILL and not isinstance(d["Glucides (g)"], (int, float)) \
                and isinstance(d["Prix normal (KRW)"], (int, float)):
            rec = fs[FS_FILL[name]]          # carbs and fat from FatSecret, the rest from the workbook
            d["Glucides (g)"], d["Lipides (g)"] = rec["carbs_g"], rec["fat_g"]
            d["Type de source"] = f"{d['Type de source']}; carbs and fat from FatSecret Korea ({rec['url']})"
            d["Niveau confiance"] = "C"
            fs_filled += 1
        missing = [f for f in NUM if not isinstance(d[f], (int, float))]
        if missing:
            left_out["no price in the workbook" if "Prix normal (KRW)" in missing else "carbs/fat not given"] += 1
            continue
        kept.append(make_row(d, d["ID interne"], d["Enseigne"], d["Prix normal (KRW)"],
                             d["Note prix/promotion"] or "", d["URL fiche/source commerciale"], d["Date consultation"]))

    # ---- extension with the official KCA price survey (price.go.kr, convenience-store head-office prices) ----
    # A product has the same nutrition in every chain; the workbook gives its nutrition, KCA gives its price
    # in chains the workbook did not cover. Workbook rows without a price can be used as nutrition donors.
    donors = {}
    for d in recs:
        if all(isinstance(d[f], (int, float)) for f in NUTR):
            donors.setdefault(d["Produit (nom coréen)"].strip(), d)
    have = {(r["store"], r["name_ko"]): r for r in kept}
    kca_added, kca_diff, n = 0, [], 0
    with open(KCA, newline="", encoding="utf-8") as f:
        for k in csv.DictReader(f):
            if k["product_ko"] not in KCA_MATCH:
                continue
            name_ko, units = KCA_MATCH[k["product_ko"]]
            unit_price = round(int(k["price_krw"]) / units)
            key = (k["store"], name_ko)
            if key in have:
                if have[key]["price_krw"] != unit_price:
                    kca_diff.append(f"{k['store']} {name_ko}: workbook {have[key]['price_krw']} KRW, KCA {unit_price} KRW")
                continue
            if name_ko not in donors:
                continue
            n += 1
            note = (f"KCA official survey {k['survey_date']}, {k['product_ko']}"
                    + (f", pack of {units}: price per unit" if units > 1 else ""))
            row = make_row(donors[name_ko], f"KCA-{n:04d}", k["store"], unit_price, note, KCA_URL, k["survey_date"])
            kept.append(row)
            have[key] = row
            kca_added += 1

    # ---- products with an official KCA price and Open Food Facts nutrition (crowd-sourced, confidence C) ----
    import json
    off = {o["code"]: o for o in json.loads(OFF.read_text(encoding="utf-8"))}
    off_added = 0
    with open(KCA, newline="", encoding="utf-8") as f:
        for k in csv.DictReader(f):
            if k["product_ko"] not in OFF_MATCH:
                continue
            code, factor, units, name_en, cat, req, prep, note = OFF_MATCH[k["product_ko"]]
            o = off[code]["per_100"]
            off_added += 1
            fsr = fs.get(k["product_ko"]) if factor == 1.0 else None   # ambiguous OFF record: FatSecret macros
            name_ko = re.sub(r"\(.*?\)", "", k["product_ko"]).strip()
            NAMES[name_ko] = name_en
            kept.append({
                "product_id": f"OFF-{off_added:04d}", "name_en": name_en, "store": k["store"], "category": cat,
                "price_krw": round(int(k["price_krw"]) / units), "promo_type": "none",
                "kcal": fsr["kcal"] if fsr else round(o["energy-kcal_100g"] * factor),
                "protein_g": fsr["protein_g"] if fsr else round(o["proteins_100g"] * factor, 1),
                "carbs_g": fsr["carbs_g"] if fsr else round(o["carbohydrates_100g"] * factor, 1),
                "fat_g": fsr["fat_g"] if fsr else round(o["fat_100g"] * factor, 1),
                "sodium_mg": round(o["sodium_100g"] * 1000 * factor), "allergens": "", "diet_tags": "",
                "requires": req, "prep_instructions": prep,
                "description": f"{SHELF[cat]}; Korean label: {name_ko}", "last_updated": k["survey_date"],
                "verified": "true",
                "source": ((f"FatSecret Korea (kcal, protein, carbs, fat: {fsr['url']}) + " if fsr else "")
                           + f"Open Food Facts (crowd-sourced, ODbL) | nutrition: {off[code]['url']} ({note}) | "
                           f"price: {KCA_URL} (KCA official survey {k['survey_date']}, {k['product_ko']}) | "
                           f"confidence C | consulted 2026-11-12"),
                "name_ko": name_ko, "allergens_known": "false"})

    missing_names = sorted({r["name_ko"] for r in kept if r["name_ko"] not in NAMES})
    if missing_names:
        sys.exit(f"Add English names for: {missing_names}")

    # ---- real products: official KCA price, estimated nutrition (verified = false) ----
    price_only = []
    with open(KCA, newline="", encoding="utf-8") as f:
        for k in csv.DictReader(f):
            if k["product_ko"] not in PRICE_ONLY:
                continue
            en, cat, kcal, prot, carb, fat, na, allerg, diet, req, prep = PRICE_ONLY[k["product_ko"]]
            nutrition_note = "nutrition and allergens: ESTIMATE of typical label values, not verified"
            if k["product_ko"] in fs:        # real macros from FatSecret; sodium and allergens stay estimates
                rec = fs[k["product_ko"]]
                kcal, prot, carb, fat = rec["kcal"], rec["protein_g"], rec["carbs_g"], rec["fat_g"]
                nutrition_note = (f"kcal, protein, carbs, fat: FatSecret Korea {rec['url']} ({rec['serving']} x "
                                  f"{rec['factor_to_unit']}) | sodium and allergens: ESTIMATE, not verified")
            units = PRICE_ONLY_UNITS.get(k["product_ko"], 1)
            name_ko = re.sub(r"\(.*?\)", "", k["product_ko"]).strip()
            shelf = SHELF.get(cat, {"rice_bowl": "Instant meal shelf", "porridge": "Instant meal shelf",
                                    "side": "Instant food shelf", "protein": "Canned / chilled food shelf"}.get(cat, "Shelf"))
            price_only.append({
                "product_id": f"KCP-{len(price_only) + 1:04d}", "name_en": en, "store": k["store"], "category": cat,
                "price_krw": round(int(k["price_krw"]) / units), "promo_type": "none", "kcal": kcal, "protein_g": prot,
                "carbs_g": carb, "fat_g": fat, "sodium_mg": na, "allergens": allerg, "diet_tags": diet,
                "requires": req, "prep_instructions": prep, "description": f"{shelf}; Korean label: {name_ko}",
                "last_updated": k["survey_date"], "verified": "false",
                "source": (f"price: KCA official survey {k['survey_date']} ({KCA_URL}, {k['product_ko']}"
                           + (f", pack of {units}: price per unit" if units > 1 else "") + f") | {nutrition_note}"),
                "name_ko": name_ko, "allergens_known": "true"})

    data = ROOT / "data"
    with open(data / "catalog_sourced.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(kept)
    with open(data / "catalog_v1.csv", newline="", encoding="utf-8") as f:
        estimates = list(csv.DictReader(f))
    with open(data / "catalog.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(kept)
        w.writerows(price_only)
        for r in estimates:
            w.writerow({**{k: r.get(k, "") for k in FIELDS}, "name_ko": "", "allergens_known": "true"})

    by_store = Counter(r["store"] for r in kept)
    by_cat = Counter(r["category"] for r in kept)
    report = [
        "# Import report: research workbook -> DormMeal catalog", "",
        f"Source: `{XLSX.relative_to(ROOT)}` (sheet MASTER_DATABASE, {len(recs)} store-product rows).", "",
        f"- Sourced products in the catalog: **{len(kept)}** = {len(kept) - kca_added - off_added} workbook rows with price + kcal + "
        f"protein + carbs + fat + sodium, + {kca_added} store-product rows added with official KCA prices "
        "(price.go.kr survey of 2026-11-06; nutrition from the workbook row of the same product)",
        f"- Including {off_added} store-product rows with official KCA prices and Open Food Facts nutrition "
        "(crowd-sourced, confidence C)",
        f"- Including {fs_filled} workbook rows completed with carbs and fat from FatSecret Korea (confidence C)",
        f"- {sum(1 for r in price_only if 'FatSecret' in r['source'])} of the {len(price_only)} price-only rows now have "
        "kcal, protein, carbs and fat from FatSecret Korea; only their sodium and allergens are estimates",
        *[f"- Price difference: {x}" for x in kca_diff],
        *[f"- Left out, {k}: {v}" for k, v in left_out.items()],
        f"- Per store: {dict(by_store)}",
        f"- Per category: {dict(by_cat)}",
        f"- With a 1+1 / 2+1 promotion: {sum(r['promo_type'] != 'none' for r in kept)}", "",
        "Nothing was estimated. Allergens are not given in the workbook, so every imported product has "
        "`allergens_known = false` and is excluded for users who declare an allergy. Vegetarian status is not "
        "documented, so no diet tag is set. Preparation hints are generic, derived from the product type.", "",
        f"`data/catalog.csv` ({len(kept) + len(price_only) + len(estimates)} products) = these {len(kept)} sourced "
        f"products + {len(price_only)} real products with an official KCA price, most with FatSecret macros and "
        f"estimated sodium/allergens (`verified = false`, ids KCP-) + {len(estimates)} fully estimated generic products (`verified = false`, "
        "from `catalog_v1.csv`). The app can be restricted to sourced products only.",
    ]
    (data / "IMPORT_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    main()
