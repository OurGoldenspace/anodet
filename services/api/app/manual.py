from __future__ import annotations

from app.store import get_manual, save_manual

# Authored for this sample fleet. Not an OEM publication.
# Section 4.2 lists the expensive check first on purpose, so a shop correction can matter.

SECTIONS: dict[str, dict[str, object]] = {
    "degradation": {
        "id": "4.2",
        "title": "Hot-section wear",
        "steps": [
            "Book a borescope of the high-pressure turbine before the next dispatch.",
            "After the borescope is scheduled, record corrected fan speed (NRf) and physical fan speed (Nf).",
            "Check LPT coolant bleed (W32) only once the borescope slot is confirmed.",
        ],
    },
    "sensor": {
        "id": "4.3",
        "title": "Single-channel fault",
        "steps": [
            "Compare the suspect channel with its pair on the same engine.",
            "Swap the connector and read the channel again before opening the case.",
            "Replace the probe only if the swap follows the fault.",
        ],
    },
    "shop": {
        "id": "S.1",
        "title": "Shop procedure",
        "steps": [
            "Confirm the asset is at the same load as the healthy runs the shop marked.",
            "Read the channels that left the healthy band before opening the case.",
            "Do the cheapest confirming check before a workshop tear-down.",
        ],
    },
    "mixed": {
        "id": "4.4",
        "title": "Mixed drift",
        "steps": [
            "Confirm the engine was in the same operating condition as the baseline.",
            "Repeat the snapshot for ten cycles before writing a shop order.",
            "Escalate to section 4.2 only if three or more channels keep the wear directions.",
        ],
    },
}

REVIEWED_HOT_SECTION_STEPS = [
    "Check LPT coolant bleed (W32) on wing. This is the cheap check.",
    "Confirm corrected fan speed (NRf) and physical fan speed (Nf) are both high.",
    "Borescope the hot section only if the bleed and both speeds confirm wear.",
]


def section_for(pattern: str) -> dict[str, object]:
    key = pattern if pattern in SECTIONS else "mixed"
    stored = get_manual(key)
    if stored is not None:
        return stored
    chosen = SECTIONS[key]
    return {
        "pattern": key,
        "id": chosen["id"],
        "title": chosen["title"],
        "source": "Shop manual" if key == "shop" else "Sample shop manual",
        "steps": list(chosen["steps"]),
    }


def update_section(pattern: str, steps: list[str]) -> dict[str, object]:
    if pattern not in SECTIONS:
        raise ValueError("That manual section is not on this fleet.")
    cleaned = [step.strip() for step in steps if step.strip()]
    if not cleaned:
        raise ValueError("The manual needs at least one step.")
    save_manual(pattern, cleaned)
    return section_for(pattern)


def save_shop_procedure(title: str, section_id: str, steps: list[str]) -> dict[str, object]:
    cleaned = [step.strip() for step in steps if step.strip()]
    if len(cleaned) < 2:
        raise ValueError("The shop procedure needs at least two steps.")
    from app.store import upsert_manual

    upsert_manual("shop", section_id[:12] or "S.1", title[:80] or "Shop procedure", cleaned[:8])
    return section_for("shop")
