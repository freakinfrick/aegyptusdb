"""
graph/kit.py — Python-side mirror of web/kit/kit.json.

Loads the canonical JSON (web/kit/kit.json) and exposes constants the
graph builder (builder_v4.py) and verifier use:

  PART_FOOTPRINT      role -> int (tiles)
  ROLE_TABLE          role -> full dict from kit.json
  PACKING_DENSITY     float
  HALL_STYLES         dict of style_key -> {tl,tr,bl,br,h,v,inner}
  TEXT_BEARING_ROLES  set of roles that MUST carry canonical_id
  text_type_to_part() corpus text_type -> part role

The JSON is the single source of truth. Do not edit constants here;
edit web/kit/kit.json and both JS + Python will pick it up.

§5, §19.5 of project-spec.md.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

KIT_JSON_PATH = Path(__file__).parent.parent / "web" / "kit" / "kit.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    with open(KIT_JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _kit() -> dict:
    return _load()


# ── Core tables ────────────────────────────────────────────────────────────

def role_table() -> dict[str, dict]:
    """Full role -> part dict."""
    return _kit()["parts"]


ROLE_TABLE = role_table()

PART_FOOTPRINT: dict[str, int] = {
    role: p.get("footprint", p.get("w", 1) * p.get("h", 1))
    for role, p in ROLE_TABLE.items()
}

PACKING_DENSITY: float = _kit()["packing_density"]

HALL_STYLES: dict[str, dict] = _kit()["hall_styles"]

TEXT_BEARING_ROLES: set[str] = set(_kit()["text_bearing_roles"])

CATEGORIES: list[str] = _kit()["categories"]

PLACEMENT_ORDER: list[str] = _kit()["placement_order"]

_TEXT_TYPE_TO_PART: dict[str, str] = _kit()["text_type_to_part"]


# ── Helpers ────────────────────────────────────────────────────────────────

def text_type_to_part(text_type: str) -> str:
    """Map a corpus text_type value to a kit part role.

    Unknown / null text_types default to `papyrus_tablet` — the most
    common storage part. Builder should avoid calling this with junk;
    validate text_type values against the keys of _TEXT_TYPE_TO_PART first.
    """
    if not text_type:
        return "papyrus_tablet"
    return _TEXT_TYPE_TO_PART.get(text_type, "papyrus_tablet")


def parts_by_category(category: str) -> list[str]:
    """List part roles in a given category (STRUCTURE / CIRCULATION / …)."""
    return [role for role, p in ROLE_TABLE.items() if p.get("cat") == category]


def is_text_bearing(role: str) -> bool:
    return role in TEXT_BEARING_ROLES


def is_walkable(role: str) -> bool:
    w = ROLE_TABLE.get(role, {}).get("walk")
    # "center_only" (portal frame) counts as non-walkable for assembler
    # simplicity; the frame renderer handles the centre tile specially.
    return w is True


def attach_of(role: str) -> str:
    return ROLE_TABLE.get(role, {}).get("attach", "floor")


# ── Sizing (§19.5 Rule 3) ──────────────────────────────────────────────────

ROOM_MIN_W, ROOM_MAX_W = 12, 64
ROOM_MIN_H, ROOM_MAX_H = 8, 44


def compute_aspect(composition: dict[str, int]) -> float:
    """Bias room aspect ratio by dominant storage attachment.

    Wall-heavy composition (papyri, inscriptions, false doors) →
      wider rectangle (aspect > 1).
    Floor-heavy (pedestals, steles, coffins) →
      squarer (aspect ~ 1.0).
    Few large pieces → squarer, a bit wider than tall.
    """
    wall_weight = 0.0
    floor_weight = 0.0
    for part_role, n in composition.items():
        role = text_type_to_part(part_role) if part_role in _TEXT_TYPE_TO_PART else part_role
        if role not in ROLE_TABLE:
            continue
        att = attach_of(role)
        fp = PART_FOOTPRINT.get(role, 1) * n
        if att in ("wall", "wall_sunken", "wall_band", "shell", "above_gateway"):
            wall_weight += fp
        else:
            floor_weight += fp
    total = wall_weight + floor_weight
    if total <= 0:
        return 1.2
    wall_frac = wall_weight / total
    # aspect ranges 1.0 (square) ↔ 1.8 (wide)
    return 1.0 + 0.8 * wall_frac


def size_room_for(composition: dict[str, int]) -> tuple[int, int]:
    """Return (w, h) in tiles, sized to exactly accommodate composition
    with architectural breathing room — never padded, never cramped.
    §19.5 Rule 3.
    """
    footprint = 0
    for part_role, n in composition.items():
        role = text_type_to_part(part_role) if part_role in _TEXT_TYPE_TO_PART else part_role
        footprint += PART_FOOTPRINT.get(role, 1) * n
    if footprint <= 0:
        return ROOM_MIN_W, ROOM_MIN_H

    floor_tiles = footprint / PACKING_DENSITY
    aspect = compute_aspect(composition)
    w = max(ROOM_MIN_W, min(ROOM_MAX_W, round(math.sqrt(floor_tiles * aspect))))
    h = max(ROOM_MIN_H, min(ROOM_MAX_H, round(math.sqrt(floor_tiles / aspect))))
    return w, h


# ── Verifier (§19.5.5) ─────────────────────────────────────────────────────

class ChamberFitError(AssertionError):
    pass


def verify_composition(
    composition: dict[str, int],
    assigned_ids: list[str],
) -> None:
    """Cheap pre-render check: the text budget must match the parts budget.

    Every text-bearing part gets exactly one canonical_id. Composition
    totals over text-bearing parts must equal len(assigned_ids).
    """
    if len(assigned_ids) != len(set(assigned_ids)):
        raise ChamberFitError(
            f"duplicate canonical_ids in assigned_ids: "
            f"{len(assigned_ids)} entries, {len(set(assigned_ids))} unique"
        )
    # Map composition text_type counts to part counts, drop non-text-bearing.
    text_part_total = 0
    for key, n in composition.items():
        role = text_type_to_part(key) if key in _TEXT_TYPE_TO_PART else key
        if role in TEXT_BEARING_ROLES:
            text_part_total += n
    if text_part_total != len(assigned_ids):
        raise ChamberFitError(
            f"composition expects {text_part_total} text-bearing parts "
            f"but assigned_ids has {len(assigned_ids)}"
        )


def density_for(composition: dict[str, int], w: int, h: int) -> float:
    footprint = 0
    for key, n in composition.items():
        role = text_type_to_part(key) if key in _TEXT_TYPE_TO_PART else key
        footprint += PART_FOOTPRINT.get(role, 1) * n
    return footprint / max(1, w * h)


def verify_density(composition: dict[str, int], w: int, h: int) -> None:
    d = density_for(composition, w, h)
    if d < 0.22 or d > 0.45:
        raise ChamberFitError(
            f"floor density {d:.3f} outside 0.22-0.45 "
            f"(w={w}, h={h}, composition={composition})"
        )


# ── Self-check on import ───────────────────────────────────────────────────

def _self_check() -> None:
    kit = _kit()
    # Every text_bearing role must exist in parts.
    for role in TEXT_BEARING_ROLES:
        assert role in ROLE_TABLE, f"text_bearing_roles refers to unknown '{role}'"
    # Every part must have a category in CATEGORIES.
    for role, p in ROLE_TABLE.items():
        assert p.get("cat") in CATEGORIES, f"part '{role}' has invalid category {p.get('cat')!r}"
    # Every text_type_to_part target must exist.
    for tt, role in _TEXT_TYPE_TO_PART.items():
        assert role in ROLE_TABLE, f"text_type_to_part['{tt}'] -> unknown role '{role}'"


_self_check()


if __name__ == "__main__":
    # Quick dump for sanity.
    print(f"kit v{_kit().get('version','?')}")
    print(f"parts: {len(ROLE_TABLE)}, text-bearing: {len(TEXT_BEARING_ROLES)}")
    for cat in CATEGORIES:
        members = parts_by_category(cat)
        print(f"  {cat:<12} {len(members):>3}  {', '.join(members[:6])}{'…' if len(members)>6 else ''}")
    # Sample sizing
    for comp in [
        {"papyrus": 3},
        {"papyrus": 14, "Wand": 6, "Schriftrolle": 2, "Sarg": 1},
        {"papyrus": 40},
    ]:
        w, h = size_room_for(comp)
        d = density_for(comp, w, h)
        print(f"  size {comp!r:<60} -> {w:>3}x{h:<3}  density={d:.3f}")
