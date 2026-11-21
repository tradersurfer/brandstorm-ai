"""Curated word banks for the combinatorial name generator.

Banks are grouped by brand aesthetic from the brief. Generation is
deterministic/combinatorial — no LLM is wired. An LLM generator can be
plugged in later behind the same interface (see generator.py).

Nothing in this file is tied to any specific brand, business, or place.
Anchor words (the must-use tokens) come ONLY from the user's brief —
see generator.py. These banks are generic roots any brief can draw on.
"""

# Roots grouped by aesthetic. A brief may select any subset; the
# generator pools the selected aesthetics and de-duplicates.
ROOTS_BY_AESTHETIC = {
    "Trendy": [
        "District", "Wave", "Nova", "Flux", "Vibe", "Slate", "Onyx",
        "Echo", "Halo", "Zenith", "Drift", "Mode", "Pulse", "Apex",
    ],
    "Minimalist": [
        "Standard", "Form", "Line", "Mono", "Bare", "True", "Core",
        "Clean", "Pure", "Plain", "Essential", "Basic",
    ],
    "High-End": [
        "Atelier", "Maison", "Luxe", "Heritage", "Reserve", "Noble",
        "Sovereign", "Prestige", "Couture", "Signature", "Opulent", "Regal",
    ],
    "Urban Utility": [
        "Supply", "Utility", "Works", "Forge", "Union", "Yard", "Depot",
        "Field", "Rig", "Outpost", "District", "Standard",
    ],
    "Rustic": [
        "Barn", "Field", "Creek", "Timber", "Stone", "Harvest", "Meadow",
        "Ridge", "Cedar", "Ember", "Prairie", "Juniper",
    ],
    "Artisan": [
        "Craft", "Makers", "Workshop", "Studio", "Forge", "Kiln", "Loom",
        "Press", "Guild", "Works", "Handmade", "Atelier",
    ],
    "Modern": [
        "North", "Atlas", "Mono", "Form", "Grid", "Pixel", "Nova", "Arc",
        "Shift", "Mode", "Signal", "Vector",
    ],
    "Playful": [
        "Sunny", "Happy", "Bright", "Zippy", "Peachy", "Bubbly", "Jolly",
        "Merry", "Lively", "Zest", "Pop", "Fizz",
    ],
}

# Optional third token for 3-word compounds.
SUFFIXES = [
    "Supply", "Co", "Studio", "Club", "Collective", "Goods", "Society",
    "Lab", "Apparel", "District", "Atelier", "Works", "Line", "Standard",
    "Union", "Threads", "Made", "Outfit",
]

# Words that make a name read as generic / collide easily — the generator
# never emits a name that is ONLY one of these, and compound structure is
# enforced (every name is 2+ tokens).
GENERIC_SINGLE_WORDS = {"Supply", "District", "Standard", "Apparel", "Club"}
