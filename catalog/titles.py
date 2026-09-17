"""Generates served titles from product_type + structured attributes only.

Never touches ABO's `item_name` field — per §5.3 that field is dense with
real brand names ("Amazon Brand - find. Women's Leather..."). Titles are
built purely from a human-readable noun for the product_type plus
brand-scrubbed color/material/style attributes actually present on the
listing, so a title with no usable attributes still reads as a title
("Ceramic Table Lamp") rather than degrading to just the bare noun.
"""
from __future__ import annotations

import random
import re

from catalog.brands import strip_known_brand_strings

NOUN = {
    "CHAIR": "Chair", "SOFA": "Sofa", "TABLE": "Table", "STOOL_SEATING": "Stool",
    "OTTOMAN": "Ottoman", "HOME_FURNITURE_AND_DECOR": "Accent Piece", "DESK": "Desk",
    "BENCH": "Bench", "SHELF": "Shelf", "CABINET": "Cabinet", "DRESSER": "Dresser",
    "HOME_MIRROR": "Mirror", "BOOKEND": "Bookend Set", "UTILITY_CART_WAGON": "Utility Cart",
    "FURNITURE_COVER": "Furniture Cover", "STORAGE_HOOK": "Storage Hook",
    "STORAGE_BOX": "Storage Box", "STORAGE_BINDER": "Binder", "HARDWARE_HANDLE": "Cabinet Handle",
    "HARDWARE": "Hardware Set", "HOME_BED_AND_BATH": "Bath Accessory", "BED": "Bed",
    "BED_FRAME": "Bed Frame", "HEADBOARD": "Headboard", "PILLOW": "Throw Pillow",
    "RUG": "Area Rug", "WALL_ART": "Wall Art Print", "VASE": "Vase", "HOME": "Home Accent",
    "SWATCH": "Fabric Swatch", "LIGHT_FIXTURE": "Light Fixture", "LAMP": "Table Lamp",
    "HOME_LIGHTING_AND_LAMPS": "Lamp", "LIGHT_BULB": "LED Bulb",
    "SHOES": "Shoes", "SANDAL": "Sandals", "BOOT": "Boots",
    "TECHNICAL_SPORT_SHOE": "Trainers",
    "FINERING": "Ring", "FINENECKLACEBRACELETANKLET": "Necklace", "FINEEARRING": "Earrings",
    "EARRING": "Earrings", "HANDBAG": "Handbag", "HAT": "Hat", "SUSPENDER": "Suspenders",
    "BEAUTY": "Beauty Essential", "SKIN_CLEANING_AGENT": "Facial Cleanser",
    "SKIN_CLEANING_WIPE": "Cleansing Wipes", "SKIN_MOISTURIZER": "Moisturizer",
    "SHAMPOO": "Shampoo", "CONDITIONER": "Conditioner", "SUNSCREEN": "Sunscreen",
    "RAZOR_BLADE_CARTRIDGE": "Razor Refill Cartridges",
    "HEALTH_PERSONAL_CARE": "Wellness Essential", "VITAMIN": "Vitamin Supplement",
    "NUTRITIONAL_SUPPLEMENT": "Nutritional Supplement", "HERBAL_SUPPLEMENT": "Herbal Supplement",
    "MINERAL_SUPPLEMENT": "Mineral Supplement", "PROTEIN_SUPPLEMENT_POWDER": "Protein Powder",
    "MEDICATION": "Wellness Aid",
    "PET_SUPPLIES": "Pet Supply", "PET_PEST_CONTROL": "Pet Pest Control",
    "OUTDOOR_LIVING": "Outdoor Living Piece", "PLANTER": "Planter",
    "ARTIFICIAL_PLANT": "Faux Plant", "OUTDOOR_RECREATION_PRODUCT": "Outdoor Gear",
    "TENT": "Tent", "FREESTANDING_SHELTER": "Canopy Shelter", "ELECTRIC_FAN": "Fan",
    "OFFICE_PRODUCTS": "Office Supply", "OFFICE_ELECTRONICS": "Office Electronic",
    "WRITING_INSTRUMENT": "Pen", "MARKING_PEN": "Marker Set", "INPUT_PEN": "Stylus",
    "LABEL": "Label Set", "TEACHING_EQUIPMENT": "Teaching Aid", "ABIS_BOOK": "Book",
    "GROCERY": "Pantry Item", "COFFEE": "Coffee", "TEA": "Tea", "BREAD": "Bread",
    "SAUCE": "Sauce", "DAIRY_BASED_DRINK": "Dairy Drink", "DAIRY_BASED_CHEESE": "Cheese",
    "DAIRY_BASED_CREAM": "Cream", "DAIRY_BASED_ICE_CREAM": "Ice Cream",
    "SNACK_MIX": "Snack Mix", "SNACK_CHIP_AND_CRISP": "Chips", "VEGETABLE": "Vegetable",
    "FRUIT": "Fruit", "EDIBLE_OIL_VEGETABLE": "Cooking Oil", "NOODLE": "Noodles",
    "LEGUME": "Legumes", "BREAKFAST_CEREAL": "Cereal", "COOKIE": "Cookies", "CAKE": "Cake Mix",
    "CRACKER": "Crackers", "JUICE_AND_JUICE_DRINK": "Juice", "PACKAGED_SOUP_AND_STEW": "Soup",
    "SALAD_DRESSING": "Salad Dressing", "HERB": "Dried Herb", "NUT_BUTTER": "Nut Butter",
    "NUTS": "Nuts", "WATER": "Water", "DRINK_FLAVORED": "Flavored Drink Mix",
    "POULTRY": "Poultry", "SHELLFISH": "Shellfish", "PANTRY": "Pantry Staple",
    "SPORTING_GOODS": "Sporting Good", "EXERCISE_MAT": "Exercise Mat",
    "EXERCISE_BAND": "Resistance Band", "FITNESS_BENCH": "Fitness Bench",
    "FISHING_EQUIPMENT": "Fishing Gear", "FISH": "Aquarium Fish Supply",
    "COMPUTER_ADD_ON": "Computer Accessory", "CELLULAR_PHONE_CASE": "Phone Case",
    "WIRELESS_ACCESSORY": "Wireless Accessory", "PORTABLE_ELECTRONIC_DEVICE_COVER": "Device Cover",
    "ELECTRONIC_ADAPTER": "Adapter", "BATTERY": "Battery Pack",
    "FLAT_SCREEN_DISPLAY_MOUNT": "TV Mount", "SPEAKERS": "Speaker",
    "VIDEO_GAME_ACCESSORIES": "Gaming Accessory", "ABIS_VIDEO_GAMES": "Video Game",
    "TOYS_AND_GAMES": "Toy", "PUZZLES": "Puzzle", "TOY_SLIME": "Slime Toy",
    "TOY_BUILDING_BLOCK": "Building Block Set",
    "LUGGAGE": "Luggage", "SUITCASE": "Suitcase", "BACKPACK": "Backpack",
    "INSTRUMENT_PARTS_AND_ACCESSORIES": "Instrument Accessory",
    "PERCUSSION_INSTRUMENTS": "Percussion Instrument",
    "AUTO_ACCESSORY": "Auto Accessory", "AUTO_PART": "Auto Part", "TOOLS": "Tool",
    "SAFETY_SUPPLY": "Safety Supply", "JANITORIAL_SUPPLY": "Cleaning Supply",
    "CLEANING_AGENT": "Cleaning Spray", "LAUNDRY_DETERGENT": "Laundry Detergent",
    "WASTE_BAG": "Waste Bags", "FOOD_STORAGE_BAG": "Food Storage Bags",
    "FOOD_SERVICE_SUPPLY": "Food Service Supply", "DRINKING_CUP": "Drinking Cup",
    "KITCHEN": "Kitchen Tool", "MAJOR_HOME_APPLIANCES": "Home Appliance",
    "ACCESSORY": "Accessory", "ACCESSORY_OR_PART_OR_SUPPLY": "Replacement Part",
    "POWERSPORTS_VEHICLE_PART": "Vehicle Part",
}

_SIZE_UNITS = {"inches", "in", "cm", "ft", "feet"}

# A "style" or "pattern" field is sometimes actually a manufacturer model
# code ("Um1530", "Basil-1W501") rather than a human descriptor. Not a
# brand-safety issue (it isn't a real brand string) but it reads as a
# stray SKU in a title, which is a craft/realism defect — filtered out
# rather than used as a title descriptor.
_SKU_LIKE = re.compile(r"^[a-z]{0,4}-?\d+[a-z0-9-]*$", re.IGNORECASE)


def _looks_like_sku(value: str) -> bool:
    return bool(_SKU_LIKE.match(value.replace(" ", "")))


def _clean(value: str, raw_brand_values: list[str]) -> str:
    value = strip_known_brand_strings(value, raw_brand_values)
    return value.strip(" -,")


def _first_en(field_values: list[dict]) -> str | None:
    for entry in field_values or []:
        tag = entry.get("language_tag", "")
        if tag.startswith("en"):
            v = entry.get("value")
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


def _first_en_list(field_values: list[dict]) -> list[str]:
    return [
        e["value"].strip()
        for e in (field_values or [])
        if e.get("language_tag", "").startswith("en") and isinstance(e.get("value"), str) and e["value"].strip()
    ]


def generate_title(listing: dict, product_type: str, rng: random.Random) -> str:
    noun = NOUN.get(product_type, product_type.replace("_", " ").title())
    raw_brand_values = [b.get("value", "") for b in listing.get("brand", [])]

    color = _clean(_first_en(listing.get("color", [])) or "", raw_brand_values)
    material = _clean(_first_en(listing.get("material", [])) or "", raw_brand_values)
    style = _clean(_first_en(listing.get("style", [])) or "", raw_brand_values)
    pattern = _clean(_first_en(listing.get("pattern", [])) or "", raw_brand_values)

    descriptors = []
    for candidate in (material, style, pattern):
        if (
            candidate
            and len(candidate) < 28
            and candidate.lower() not in noun.lower()
            and not _looks_like_sku(candidate)
        ):
            descriptors.append(candidate)
    lead = descriptors[0].title() if descriptors else ""

    title = f"{lead} {noun}".strip() if lead else noun

    tail_parts = []
    if color and color.lower() not in title.lower() and len(color) < 24:
        tail_parts.append(color.title())

    if not lead and not tail_parts:
        # Nothing distinguishes this title from every other item of the
        # same product_type yet — pull one differentiator from the
        # (brand-scrubbed) keyword list rather than serving a bare noun.
        for kw in _first_en_list(listing.get("item_keywords", [])):
            kw_clean = _clean(kw, raw_brand_values)
            if (
                kw_clean
                and 3 <= len(kw_clean) <= 24
                and kw_clean.lower() not in title.lower()
                and not _looks_like_sku(kw_clean)
                and not any(w in kw_clean.lower() for w in ("women", "men", "kids"))
            ):
                tail_parts.append(kw_clean.title())
                break

    dims = listing.get("item_dimensions")
    size_str = None
    if isinstance(dims, dict):
        length = dims.get("length", {}).get("normalized_value", {})
        if length.get("unit") in _SIZE_UNITS and length.get("value"):
            size_str = f"{length['value']:g}{'in' if length['unit'].startswith('in') else length['unit']}"

    if tail_parts:
        title = f"{title}, {', '.join(tail_parts)}"
    if size_str:
        title = f"{title} ({size_str})"

    # Collapse accidental double spaces from scrubbing, cap length.
    title = " ".join(title.split())
    if len(title) > 80:
        title = title[:77].rstrip() + "..."
    return title
