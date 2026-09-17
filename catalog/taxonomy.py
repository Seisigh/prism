"""Maps ABO's `product_type` vocabulary onto PRISM's own category tree,
interest verticals, gender-coding and default age band.

This mapping is hand-authored against the real distribution of US, valid
(name + image + brand present) ABO listings — see STATE.md for the coverage
audit. ABO is a furniture/home/apparel/grocery-heavy dataset with almost no
gaming, music, reading/study or crafts inventory; §5.2's 15-25-per-cell
target is explicitly a soft target ("thin for measurement, correct for
context"), and several vertical x demographic cells will be thin by
necessity of the source data, not by a selection bug. That's logged
honestly rather than padded with near-duplicate filler.

`CATEGORY` is the site IA (header nav, category pages). `verticals` maps a
product type onto zero or more of the 10 interest verticals in §5.2.
`gender` is "womens" | "mens" | "unisex". `age_band` is a default, refined
by keyword heuristics in select.py (kids/teen signals in title/keywords).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TypeInfo:
    category: str
    verticals: tuple[str, ...] = ()
    gender: str = "unisex"
    age_band: str = "adult"


CATEGORIES = [
    "Home & Furniture",
    "Kitchen & Dining",
    "Bed & Bath",
    "Rugs & Decor",
    "Lighting",
    "Shoes & Footwear",
    "Jewelry & Accessories",
    "Beauty & Personal Care",
    "Health & Wellness",
    "Pet Supplies",
    "Outdoor & Garden",
    "Office & Stationery",
    "Grocery & Gourmet",
    "Sports & Fitness",
    "Electronics Accessories",
    "Toys & Games",
    "Travel & Luggage",
    "Arts & Crafts",
    "Music",
]

VERTICALS = [
    "cooking",
    "fitness",
    "outdoors_camping",
    "gaming",
    "music",
    "reading_study",
    "gardening",
    "crafts",
    "pets",
    "travel",
]

# product_type -> TypeInfo. Only product types that clear the selection
# filters (US, en_* name, image, brand) and have >= 1 usable listing are
# worth mapping; unmapped types are simply excluded from the catalog.
PRODUCT_TYPE_MAP: dict[str, TypeInfo] = {
    # --- Home & Furniture ---
    "CHAIR": TypeInfo("Home & Furniture"),
    "SOFA": TypeInfo("Home & Furniture"),
    "TABLE": TypeInfo("Home & Furniture"),
    "STOOL_SEATING": TypeInfo("Home & Furniture"),
    "OTTOMAN": TypeInfo("Home & Furniture"),
    "HOME_FURNITURE_AND_DECOR": TypeInfo("Home & Furniture"),
    "DESK": TypeInfo("Home & Furniture", verticals=("reading_study",)),
    "BENCH": TypeInfo("Home & Furniture"),
    "SHELF": TypeInfo("Home & Furniture"),
    "CABINET": TypeInfo("Home & Furniture"),
    "DRESSER": TypeInfo("Home & Furniture"),
    "HOME_MIRROR": TypeInfo("Home & Furniture"),
    "BOOKEND": TypeInfo("Home & Furniture", verticals=("reading_study",)),
    "UTILITY_CART_WAGON": TypeInfo("Home & Furniture"),
    "FURNITURE_COVER": TypeInfo("Home & Furniture"),
    "STORAGE_HOOK": TypeInfo("Home & Furniture"),
    "STORAGE_BOX": TypeInfo("Home & Furniture"),
    "STORAGE_BINDER": TypeInfo("Office & Stationery", verticals=("reading_study",)),
    "HARDWARE_HANDLE": TypeInfo("Home & Furniture"),
    "HARDWARE": TypeInfo("Home & Furniture"),

    # --- Bed & Bath ---
    "HOME_BED_AND_BATH": TypeInfo("Bed & Bath"),
    "BED": TypeInfo("Bed & Bath"),
    "BED_FRAME": TypeInfo("Bed & Bath"),
    "HEADBOARD": TypeInfo("Bed & Bath"),
    "PILLOW": TypeInfo("Bed & Bath"),

    # --- Rugs & Decor ---
    "RUG": TypeInfo("Rugs & Decor"),
    "WALL_ART": TypeInfo("Rugs & Decor", verticals=("crafts",)),
    "VASE": TypeInfo("Rugs & Decor"),
    "HOME": TypeInfo("Rugs & Decor"),
    "SWATCH": TypeInfo("Rugs & Decor"),

    # --- Lighting ---
    "LIGHT_FIXTURE": TypeInfo("Lighting"),
    "LAMP": TypeInfo("Lighting"),
    "HOME_LIGHTING_AND_LAMPS": TypeInfo("Lighting"),
    "LIGHT_BULB": TypeInfo("Lighting"),

    # --- Shoes & Footwear (gender-coded) ---
    "SHOES": TypeInfo("Shoes & Footwear", gender="womens"),
    "SANDAL": TypeInfo("Shoes & Footwear", gender="womens"),
    "BOOT": TypeInfo("Shoes & Footwear", gender="womens"),
    "TECHNICAL_SPORT_SHOE": TypeInfo("Shoes & Footwear", verticals=("fitness",), gender="mens"),

    # --- Jewelry & Accessories (gender-coded) ---
    "FINERING": TypeInfo("Jewelry & Accessories", gender="womens"),
    "FINENECKLACEBRACELETANKLET": TypeInfo("Jewelry & Accessories", gender="womens"),
    "FINEEARRING": TypeInfo("Jewelry & Accessories", gender="womens"),
    "EARRING": TypeInfo("Jewelry & Accessories", gender="womens"),
    "HANDBAG": TypeInfo("Jewelry & Accessories", gender="womens"),
    "HAT": TypeInfo("Jewelry & Accessories"),
    "SUSPENDER": TypeInfo("Jewelry & Accessories", gender="mens"),

    # --- Beauty & Personal Care ---
    "BEAUTY": TypeInfo("Beauty & Personal Care"),
    "SKIN_CLEANING_AGENT": TypeInfo("Beauty & Personal Care"),
    "SKIN_CLEANING_WIPE": TypeInfo("Beauty & Personal Care"),
    "SKIN_MOISTURIZER": TypeInfo("Beauty & Personal Care"),
    "SHAMPOO": TypeInfo("Beauty & Personal Care"),
    "CONDITIONER": TypeInfo("Beauty & Personal Care"),
    "SUNSCREEN": TypeInfo("Beauty & Personal Care"),
    "RAZOR_BLADE_CARTRIDGE": TypeInfo("Beauty & Personal Care"),

    # --- Health & Wellness ---
    "HEALTH_PERSONAL_CARE": TypeInfo("Health & Wellness"),
    "VITAMIN": TypeInfo("Health & Wellness"),
    "NUTRITIONAL_SUPPLEMENT": TypeInfo("Health & Wellness"),
    "HERBAL_SUPPLEMENT": TypeInfo("Health & Wellness"),
    "MINERAL_SUPPLEMENT": TypeInfo("Health & Wellness"),
    "PROTEIN_SUPPLEMENT_POWDER": TypeInfo("Health & Wellness", verticals=("fitness",)),
    "MEDICATION": TypeInfo("Health & Wellness"),

    # --- Pet Supplies ---
    "PET_SUPPLIES": TypeInfo("Pet Supplies", verticals=("pets",)),
    "PET_PEST_CONTROL": TypeInfo("Pet Supplies", verticals=("pets",)),

    # --- Outdoor & Garden ---
    "OUTDOOR_LIVING": TypeInfo("Outdoor & Garden", verticals=("outdoors_camping", "gardening")),
    "PLANTER": TypeInfo("Outdoor & Garden", verticals=("gardening",)),
    "ARTIFICIAL_PLANT": TypeInfo("Outdoor & Garden", verticals=("gardening",)),
    "OUTDOOR_RECREATION_PRODUCT": TypeInfo("Outdoor & Garden", verticals=("outdoors_camping",)),
    "TENT": TypeInfo("Outdoor & Garden", verticals=("outdoors_camping",)),
    "FREESTANDING_SHELTER": TypeInfo("Outdoor & Garden", verticals=("outdoors_camping",)),
    "ELECTRIC_FAN": TypeInfo("Outdoor & Garden"),

    # --- Office & Stationery ---
    "OFFICE_PRODUCTS": TypeInfo("Office & Stationery", verticals=("reading_study",)),
    "OFFICE_ELECTRONICS": TypeInfo("Office & Stationery", verticals=("reading_study",)),
    "WRITING_INSTRUMENT": TypeInfo("Office & Stationery", verticals=("reading_study",)),
    "MARKING_PEN": TypeInfo("Office & Stationery", verticals=("reading_study", "crafts")),
    "INPUT_PEN": TypeInfo("Office & Stationery", verticals=("reading_study",)),
    "LABEL": TypeInfo("Office & Stationery"),
    "TEACHING_EQUIPMENT": TypeInfo("Office & Stationery", verticals=("reading_study",)),
    "ABIS_BOOK": TypeInfo("Office & Stationery", verticals=("reading_study",)),

    # --- Grocery & Gourmet ---
    "GROCERY": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "COFFEE": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "TEA": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "BREAD": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "SAUCE": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "DAIRY_BASED_DRINK": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "DAIRY_BASED_CHEESE": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "DAIRY_BASED_CREAM": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "DAIRY_BASED_ICE_CREAM": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "SNACK_MIX": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "SNACK_CHIP_AND_CRISP": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "VEGETABLE": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "FRUIT": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "EDIBLE_OIL_VEGETABLE": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "NOODLE": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "LEGUME": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "BREAKFAST_CEREAL": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "COOKIE": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "CAKE": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "CRACKER": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "JUICE_AND_JUICE_DRINK": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "PACKAGED_SOUP_AND_STEW": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "SALAD_DRESSING": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "HERB": TypeInfo("Grocery & Gourmet", verticals=("cooking", "gardening")),
    "NUT_BUTTER": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "NUTS": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "WATER": TypeInfo("Grocery & Gourmet"),
    "DRINK_FLAVORED": TypeInfo("Grocery & Gourmet"),
    "POULTRY": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "SHELLFISH": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),
    "PANTRY": TypeInfo("Grocery & Gourmet", verticals=("cooking",)),

    # --- Sports & Fitness ---
    "SPORTING_GOODS": TypeInfo("Sports & Fitness", verticals=("fitness",)),
    "EXERCISE_MAT": TypeInfo("Sports & Fitness", verticals=("fitness",)),
    "EXERCISE_BAND": TypeInfo("Sports & Fitness", verticals=("fitness",)),
    "FITNESS_BENCH": TypeInfo("Sports & Fitness", verticals=("fitness",)),
    "FISHING_EQUIPMENT": TypeInfo("Sports & Fitness", verticals=("outdoors_camping",)),
    "FISH": TypeInfo("Pet Supplies", verticals=("pets",)),

    # --- Electronics Accessories ---
    "COMPUTER_ADD_ON": TypeInfo("Electronics Accessories"),
    "CELLULAR_PHONE_CASE": TypeInfo("Electronics Accessories"),
    "WIRELESS_ACCESSORY": TypeInfo("Electronics Accessories"),
    "PORTABLE_ELECTRONIC_DEVICE_COVER": TypeInfo("Electronics Accessories"),
    "ELECTRONIC_ADAPTER": TypeInfo("Electronics Accessories"),
    "BATTERY": TypeInfo("Electronics Accessories"),
    "FLAT_SCREEN_DISPLAY_MOUNT": TypeInfo("Electronics Accessories"),
    "SPEAKERS": TypeInfo("Electronics Accessories", verticals=("music",)),
    "VIDEO_GAME_ACCESSORIES": TypeInfo("Toys & Games", verticals=("gaming",), age_band="teen"),
    "ABIS_VIDEO_GAMES": TypeInfo("Toys & Games", verticals=("gaming",), age_band="teen"),

    # --- Toys & Games ---
    "TOYS_AND_GAMES": TypeInfo("Toys & Games", verticals=("gaming",), age_band="kids"),
    "PUZZLES": TypeInfo("Toys & Games", verticals=("gaming",), age_band="kids"),
    "TOY_SLIME": TypeInfo("Toys & Games", age_band="kids"),
    "TOY_BUILDING_BLOCK": TypeInfo("Toys & Games", age_band="kids"),

    # --- Travel & Luggage ---
    "LUGGAGE": TypeInfo("Travel & Luggage", verticals=("travel",)),
    "SUITCASE": TypeInfo("Travel & Luggage", verticals=("travel",)),
    "BACKPACK": TypeInfo("Travel & Luggage", verticals=("travel", "outdoors_camping")),

    # --- Arts & Crafts ---
    "INSTRUMENT_PARTS_AND_ACCESSORIES": TypeInfo("Music", verticals=("music",)),
    "PERCUSSION_INSTRUMENTS": TypeInfo("Music", verticals=("music",)),

    # --- Auto / Misc kept in a broad bucket ---
    "AUTO_ACCESSORY": TypeInfo("Home & Furniture"),
    "AUTO_PART": TypeInfo("Home & Furniture"),
    "TOOLS": TypeInfo("Home & Furniture", verticals=("crafts",)),
    "SAFETY_SUPPLY": TypeInfo("Home & Furniture"),
    "JANITORIAL_SUPPLY": TypeInfo("Home & Furniture"),
    "CLEANING_AGENT": TypeInfo("Home & Furniture"),
    "LAUNDRY_DETERGENT": TypeInfo("Home & Furniture"),
    "WASTE_BAG": TypeInfo("Home & Furniture"),
    "FOOD_STORAGE_BAG": TypeInfo("Kitchen & Dining", verticals=("cooking",)),
    "FOOD_SERVICE_SUPPLY": TypeInfo("Kitchen & Dining", verticals=("cooking",)),
    "DRINKING_CUP": TypeInfo("Kitchen & Dining", verticals=("cooking",)),
    "KITCHEN": TypeInfo("Kitchen & Dining", verticals=("cooking",)),
    "MAJOR_HOME_APPLIANCES": TypeInfo("Kitchen & Dining", verticals=("cooking",)),
    "ACCESSORY": TypeInfo("Jewelry & Accessories"),
    "ACCESSORY_OR_PART_OR_SUPPLY": TypeInfo("Home & Furniture"),
    "POWERSPORTS_VEHICLE_PART": TypeInfo("Home & Furniture"),
}

_KIDS_KEYWORDS = ("kids", "toddler", "baby", "boys", "girls", "children", "child")
_TEEN_KEYWORDS = ("teen", "youth", "junior")
_OLDER_ADULT_KEYWORDS = ("senior", "elderly", "arthritis", "mobility aid")


def infer_age_band(default: str, text_blob: str) -> str:
    blob = text_blob.lower()
    if any(k in blob for k in _KIDS_KEYWORDS):
        return "kids"
    if any(k in blob for k in _TEEN_KEYWORDS):
        return "teen"
    if any(k in blob for k in _OLDER_ADULT_KEYWORDS):
        return "older_adult"
    return default


_WOMENS_RE = re.compile(r"\b(women'?s?|female|ladies)\b", re.IGNORECASE)
_MENS_RE = re.compile(r"(?<!wo)\bmen'?s?\b|\bmale\b", re.IGNORECASE)


def infer_gender(default: str, text_blob: str) -> str:
    """Only overrides a *gender-coded* default (womens/mens) using explicit
    keyword signal in the source text; ungendered product types stay
    unisex regardless of keyword noise."""
    if default not in ("womens", "mens"):
        return default
    has_women = bool(_WOMENS_RE.search(text_blob))
    has_men = bool(_MENS_RE.search(text_blob))
    if has_women and not has_men:
        return "womens"
    if has_men and not has_women:
        return "mens"
    return default


def lookup(product_type: str) -> TypeInfo | None:
    return PRODUCT_TYPE_MAP.get(product_type)
