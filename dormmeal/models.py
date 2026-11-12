"""Pydantic schemas shared by the catalog, tools, verifier and agent."""
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Store(str, Enum):
    CU = "CU"
    GS25 = "GS25"
    EMART24 = "Emart24"
    SEVEN_ELEVEN = "7-Eleven"


class Equipment(str, Enum):
    MICROWAVE = "microwave"
    KETTLE = "kettle"
    FRIDGE = "fridge"


class Diet(str, Enum):
    NONE = "none"
    VEGETARIAN = "vegetarian"
    HALAL_FRIENDLY = "halal_friendly"


class PromoType(str, Enum):
    NONE = "none"
    ONE_PLUS_ONE = "1+1"
    TWO_PLUS_ONE = "2+1"


class MealSlot(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"


class Product(BaseModel):
    product_id: str
    name_en: str
    store: Store
    category: str
    price_krw: int = Field(ge=0)
    promo_type: PromoType = PromoType.NONE
    kcal: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    sodium_mg: float = Field(ge=0)
    allergens: list[str] = []
    diet_tags: list[Diet] = []
    requires: list[Equipment] = []
    prep_instructions: Optional[str] = None
    description: str
    last_updated: str
    verified: bool = False  # True when price and nutrition come from an identified source for this exact product
    source: str = ""       # where the values come from (URL, label photo, ...)
    name_ko: str = ""      # Korean name as printed on the package (helps to find it in the store)
    allergens_known: bool = True  # False when the source gives no allergen information


class NutritionTargets(BaseModel):
    kcal_per_day: tuple[float, float] = (1800, 2400)
    protein_g_per_day_min: float = 60
    sodium_mg_per_day_max: float = 2300


class Constraints(BaseModel):
    weekly_budget_krw: int = Field(gt=0)
    diet: Diet = Diet.NONE
    allergies: list[str] = []
    equipment: list[Equipment] = []
    stores: list[Store] = [Store.CU, Store.GS25, Store.EMART24, Store.SEVEN_ELEVEN]
    meals_per_day: int = Field(default=3, ge=1, le=3)
    targets: NutritionTargets = NutritionTargets()
    max_repeats_per_product: int = Field(default=3, ge=1)
    disliked_product_ids: list[str] = []
    liked_product_ids: list[str] = []
    skipped_meals: list[tuple[int, MealSlot]] = []   # (day, slot) the user will not eat (replanning)
    unavailable_product_ids: list[str] = []          # sold out this week (replanning), not a dislike
    sourced_only: bool = False                       # use only products with sourced (verified) data


def active_slots(meals_per_day: int) -> list[MealSlot]:
    """Slots planned for a given number of meals per day (1 -> lunch, 2 -> lunch + dinner, 3 -> all)."""
    return {1: [MealSlot.LUNCH], 2: [MealSlot.LUNCH, MealSlot.DINNER],
            3: [MealSlot.BREAKFAST, MealSlot.LUNCH, MealSlot.DINNER]}[meals_per_day]


class PlanItem(BaseModel):
    product_id: str
    quantity: int = Field(ge=1)  # units taken home (including free units from a promo)


class Meal(BaseModel):
    day: int = Field(ge=1, le=7)
    slot: MealSlot
    items: list[PlanItem]
    locked: bool = False


class MealPlan(BaseModel):
    meals: list[Meal]


class Event(BaseModel):
    type: Literal["skip_meal", "sold_out", "budget_change", "equipment_change"]
    day: Optional[int] = None
    slot: Optional[MealSlot] = None
    product_id: Optional[str] = None
    store: Optional[Store] = None
    new_budget_krw: Optional[int] = None
    equipment: Optional[Equipment] = None      # for equipment_change
    available: Optional[bool] = None           # equipment_change: True = gained, False = lost/broken
    raw_text: str


class Violation(BaseModel):
    rule: Literal["budget", "allergen", "equipment", "diet", "nutrition", "variety", "unknown_product",
                  "store", "preference", "structure"]
    detail: str


class Totals(BaseModel):
    total_cost_krw: int
    daily_kcal: dict[int, float]
    daily_protein_g: dict[int, float]
    daily_sodium_mg: dict[int, float]
    units_per_product: dict[str, int]


class VerificationResult(BaseModel):
    valid: bool
    totals: Optional[Totals] = None
    violations: list[Violation] = []
