"""Fixed sector taxonomy.

Changing it means changing the Gemini schema, the pack's need mapping and the dashboard filters together.
"""

from typing import Literal, get_args

Sector = Literal["water", "sanitation", "roads", "health", "education", "electricity", "waste", "other"]
SECTORS: tuple[str, ...] = get_args(Sector)

SECTOR_DESCRIPTIONS: dict[str, str] = {
    "water": "Drinking water supply: taps, handpumps, tankers, water quality",
    "sanitation": "Toilets, drains, sewage, open defecation",
    "roads": "Roads, bridges, potholes, rural connectivity",
    "health": "Health centres, doctors, medicines, ambulances",
    "education": "Schools, teachers, school buildings and facilities",
    "electricity": "Household connections, outages, transformers, street lights",
    "waste": "Solid-waste collection, garbage dumps, burning",
    "other": "Anything that does not fit the sectors above",
}
