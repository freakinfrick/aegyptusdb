"""Pydantic models for the Chamber graph."""

from pydantic import BaseModel


class Corridor(BaseModel):
    target_id: str          # chamber canonical ID
    label: str              # Egyptian term connecting them (e.g. "ns · tongue")
    strength: int           # number of shared texts
    direction: str          # N/S/E/W/NE/NW/SE/SW for ASCII rendering


class ChamberNode(BaseModel):
    id: str                 # e.g. "tongue"
    name_en: str            # "CHAMBER OF THE TONGUE"
    term_eg: str            # "ns · rʾ"
    term_transliteration: str
    depth: int              # 0=surface, 5=deepest. Correlates with age.
    text_count: int
    period_range: str       # e.g. "Old Kingdom – Roman"
    canonical_ids: list[str]  # corpus IDs of texts in this chamber
    highlight_quotes: list[dict]  # [{quote, canonical_id, shelfmark, period}]
    corridors: list[Corridor]
    locked: bool = False    # true = only accessible via specific path
