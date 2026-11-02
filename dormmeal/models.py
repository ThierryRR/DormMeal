"""Pydantic schemas shared by the catalog, tools, verifier and agent."""
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Store(str, Enum):
    CU = "CU"
    GS25 = "GS25"
    EMART24 = "Emart24"


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
    verified: bool = False  # True once price and nutrition were checked against a real label


class NutritionTargets(BaseModel):
    kcal_per_day: tuple[float, float] = (1800, 2400)
    protein_g_per_day_min: float = 60
    sodium_mg_per_day_max: float = 2300


class Constraints(BaseModel):
    weekly_budget_krw: int = Field(gt=0)
    diet: Diet = Diet.NONE
    allergies: list[str] = []
    equipment: list[Equipment] = []
    stores: list[Store] = [Store.CU, Store.GS25, Store.EMART24]
    meals_per_day: int = Field(default=3, ge=1, le=3)
    targets: NutritionTargets = NutritionTargets()
    max_repeats_per_product: int = Field(default=3, ge=1)
    disliked_product_ids: list[str] = []
    liked_product_ids: list[str] = []


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
    raw_text: str


class Violation(BaseModel):
    rule: Literal["budget", "allergen", "equipment", "diet", "nutrition", "variety", "unknown_product"]
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
