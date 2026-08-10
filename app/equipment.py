from __future__ import annotations

from typing import Literal


EquipmentSlot = Literal[
    "head",
    "cape",
    "neck",
    "ammo",
    "weapon",
    "body",
    "shield",
    "legs",
    "hands",
    "feet",
    "ring",
]

EQUIPMENT_SLOTS = frozenset(
    {
        "head",
        "cape",
        "neck",
        "ammo",
        "weapon",
        "body",
        "shield",
        "legs",
        "hands",
        "feet",
        "ring",
    }
)


def normalize_wiki_slot(slot: str) -> str:
    """Translate Wiki slots to the 11 slots shown by the game interface."""

    return "weapon" if slot == "2h" else slot
