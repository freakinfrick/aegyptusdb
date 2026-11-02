# KIT-OF-PARTS — The ASCII Architecture

_Canonical catalog for the Aegyptus Labyrinth (v4.0 §5, §19.5)._

This document is the **shared language** between the graph builder
(`graph/builder_v4.py`), the room assembler (`web/game.js`
`assembleChamber`), the verifier (§19.5.5), and the side-panel UI.
Python and JS both read it. When you add a part, you add it here first.

---

## PRINCIPLES

1. **Every char has an architectural role.** No decorative noise.
2. **Every part that carries a text carries exactly one `canonical_id`.**
3. **Every part has an explicit footprint.** Width × height in tiles.
4. **Every tile has explicit walkability.** Player can walk onto
   `walk: true` tiles, never onto `walk: false`. No in-between.
5. **Parts compose — they don't clash.** Structural before circulation
   before monumental before markers. The assembler places in this order.

---

## FIVE ARCHITECTURAL CATEGORIES

Parts are grouped by *what they do in the room*, not by corpus text-type.
The mapping from corpus `text_type` → part lives in §21 Appendix A of the
spec and in `kit/text_type_to_part.py`.

```
1. STRUCTURE     — defines the room shell and load-bearing elements
2. CIRCULATION   — controls movement between + within chambers
3. STORAGE       — shelves, niches, racks — where texts are kept
4. MONUMENTAL    — freestanding or recessed text-bearing centrepieces
5. MARKER        — small floor-scatter, annotation, ornament
```

---

## 1. STRUCTURE — The shell

The room boundary and its load-bearing elements. Never carries text on
its own (inscriptions use wall-mounted STORAGE parts attached to walls).

| Role            | Char(s)         | Footprint | Walk | Notes                                    |
|-----------------|-----------------|-----------|------|------------------------------------------|
| wall_h          | `═` `─`         | 1×1       | no   | horizontal wall segment                  |
| wall_v          | `║` `│`         | 1×1       | no   | vertical wall segment                    |
| wall_corner_tl  | `╔` `┌` `╒` `╓` | 1×1       | no   | top-left corner (style per hall)         |
| wall_corner_tr  | `╗` `┐` `╕` `╖` | 1×1       | no   | top-right                                |
| wall_corner_bl  | `╚` `└` `╘` `╙` | 1×1       | no   | bottom-left                              |
| wall_corner_br  | `╝` `┘` `╛` `╜` | 1×1       | no   | bottom-right                             |
| pillar          | `║` `║` `══`    | 1×3       | no   | structural column; inscription optional  |
| pillar_capital  | `▛` `▜`         | 1×1 ×2    | no   | capital caps on a pillar (top 2 tiles)   |
| plinth          | `▬`             | 1×1       | no   | stepped base, usually under SCULPTURE    |
| architrave      | `═══════`       | 4-8×1     | no   | horizontal beam above a gateway          |
| ceiling_beam    | `━`             | N×1       | no   | visible ceiling band (level-relative)    |

Hall style lookup (from existing v3.1 `BOX` table):

```
oracle    ╔ ╗ ╚ ╝ ═ ║   inner ·
utterance ┌ ┐ └ ┘ ─ │   inner ·
body      ╒ ╕ ╘ ╛ ═ │   inner .
dead      ╓ ╖ ╙ ╜ ─ ║   inner ░
power     ╔ ╗ ╚ ╝ ═ ║   inner ▒
cosmos    ╭ ╮ ╰ ╯ ─ │   inner *
wisdom    ▛ ▜ ▙ ▟ ─ │   inner ·
```

Builder picks hall style from top lemma cluster; assembler renders.

---

## 2. CIRCULATION — Getting around

Controls how the player moves. All circulation tiles are walkable.

| Role            | Char       | Footprint | Walk | Notes                                           |
|-----------------|------------|-----------|------|-------------------------------------------------|
| floor           | `·` `.`    | 1×1       | yes  | default ground                                  |
| floor_dot       | `·`        | 1×1       | yes  | patterned floor (every 4th tile, style-driven) |
| walkway         | `▒`        | 1×1       | yes  | marked path; high-contrast wear                 |
| gateway_open    | ` `        | 1×1       | yes  | doorway opening — break in wall                 |
| gateway_arch    | `∩`        | 1×1       | yes  | arched opening (under architrave)               |
| gateway_portal  | `▣`        | 1×1       | yes  | Oracle-opened portal (v3.1 mechanic)            |
| gateway_portal_frame | `┌─┐` + `└─┘`  | 3×3 | mixed | 3×3 portal zone; only center is walkable   |
| stair_up        | `<`        | 1×1       | yes  | ascend to lower-numbered level                  |
| stair_down      | `>`        | 1×1       | yes  | descend to higher-numbered level                |
| threshold       | `═`        | 1×1       | yes  | walkable wall-tile marking room boundary        |
| corridor_h      | `═`        | N×1       | yes  | horizontal corridor between chambers            |
| corridor_v      | `║`        | 1×N       | yes  | vertical corridor                               |
| corridor_bend   | `╔╗╚╝`    | 1×1       | yes  | corridor corner turn                            |

Portals are **circulation**, not monuments. The Oracle spawns them; the
player walks through them; they vanish. The gateway_portal_frame lays
down the 3×3 zone; only the center `▣` is walkable to enterPortal().

---

## 3. STORAGE — Where texts live

Any part that holds a `canonical_id`. These are the "books" of the
library. Every chamber's text budget is spent on these parts.

| Role            | Char(s)             | Footprint | Walk | Attach | text_type hint          |
|-----------------|---------------------|-----------|------|--------|-------------------------|
| papyrus_tablet  | `▌𓀀▐` stacked 3     | 1×3       | no   | wall   | papyrus                 |
| wall_inscription| `𓈖𓇋𓏏`              | 4-8×1     | no   | wall   | Wand                    |
| scroll_pedestal | `╭╮ ║║ ▔▔`          | 1×2       | no   | floor  | Schriftrolle            |
| shelf_niche     | `│█│`               | 1×2       | no   | wall   | manuscript cache        |
| rack_vertical   | `▐▌▐▌`              | 1×3       | no   | wall   | scroll rack (Coptic)    |
| false_door      | `┌─┐ │𓉔│ └─┘`       | 2×3       | no   | wall   | Scheintür               |
| tomb_alcove     | `╔═╗ ║𓋴║ ╚═╝`       | 3×2       | no   | wall (sunken) | Grab           |
| ostrakon        | `▫`                 | 1×1       | yes* | floor  | Ostrakon                |
| doorway_lintel  | `𓉐` above threshold  | 1×1       | —    | overhead | Tür                   |
| room_band       | `𓂀𓁹`                | N×1       | no   | wall band | Raum                  |

`walk: yes*` on ostrakon means you can step onto it — scattered floor
shard, pick-uppable.

STORAGE parts attach to either `wall` or `floor`. Wall attachments fuse
into the chamber boundary during assembly (a papyrus tablet on the
north wall replaces 1×3 wall segments, not adds to them).

---

## 4. MONUMENTAL — Centrepieces

Large freestanding or wall-recessed pieces. Usually a chamber has one
monumental piece anchoring it; everything else arranges around it.

| Role      | Char(s)           | Footprint | Walk | text_type hint |
|-----------|-------------------|-----------|------|----------------|
| stele     | `╱╲ │𓊵│ └─┘`      | 1×3       | no   | Stele          |
| coffin    | `▓▓▓▓ ▓𓁷𓃀▓ ▓▓▓▓`  | 3×2       | no   | Sarg           |
| sculpture | `𓃠` big glyph     | 2×3       | no   | Skulptur       |
| vessel    | `⏣ ┻`              | 1×2       | no   | Gefäß          |
| rock_cut  | `▒▓░` irregular    | 2-4×2-4   | no   | Fels           |

MONUMENTAL carries exactly one canonical_id. Stand adjacent → wayfinder
shows passage. Large glyph in the centre tile rendered in Noto Egyptian
at 1.4× tile size.

---

## 5. MARKER — Small annotation

Sub-tile-precision elements. Mostly ornamental, but always sourced from
a real canonical_id when they carry text.

| Role          | Char     | Footprint | Walk | text_type hint |
|---------------|----------|-----------|------|----------------|
| torch         | `†`      | 1×1       | no   | —              |
| incense_brazier | `ᚖ`   | 1×1       | no   | —              |
| floor_cartouche | `⊡`  | 1×1       | yes  | named text     |
| scatter_glyph | `𓃭`     | 1×1       | yes  | small epigraph |
| direction_sign | `→↑↓←` | 1×1       | no   | Oracle hint    |

MARKERs without a canonical_id exist only in L0 Sanctum (torches,
braziers). **No marker in a non-Sanctum chamber exists without a
canonical_id.** This is Rule 4 applied at the pixel.

---

## THE ASSEMBLER CONTRACT (§5.2, §19.5.6)

```python
def assembleChamber(chamber, canonical_id_passages):
    """
    chamber.assigned_ids : list[str]     — §19.5.2 global unique assignment
    chamber.text_type_composition: dict  — e.g. {'papyrus': 14, 'Wand': 6}
    """
    # 1. Size the room from composition (§19.5 Rule 3)
    w, h = size_room_for(chamber.text_type_composition)

    # 2. Build the shell (STRUCTURE, hall style)
    place_walls(w, h, hall_style=chamber.hall_style)

    # 3. Place one-off MONUMENTAL piece if composition suggests one
    #    (sarg, sculpture, rock_cut — always centred, always single)
    if has_monumental(composition):
        place_monumental_at_center(pick_monumental(assigned_ids))

    # 4. Place STRUCTURE interior (pillars on a grid if room is wide)
    place_pillars_if_needed(w, h)

    # 5. Place STORAGE wall-attached parts — papyri, inscriptions, shelves
    #    Each consumes ONE canonical_id from assigned_ids
    for part_type, count in composition.items():
        role = text_type_to_part(part_type)   # §21 App. A mapping
        if attaches_to(role) == 'wall':
            place_n_on_walls(role, count, pop_canonical_ids())

    # 6. Place STORAGE floor-attached — pedestals, steles, racks
    for part_type, count in composition.items():
        role = text_type_to_part(part_type)
        if attaches_to(role) == 'floor':
            place_n_on_floor(role, count, pop_canonical_ids())

    # 7. Scatter remaining canonical_ids as OSTRAKA (smallest storage)
    #    until assigned_ids is exhausted
    while assigned_ids:
        place_ostrakon(pop_canonical_ids())

    # 8. Place CIRCULATION — walkways, thresholds, corridor entries
    place_gateways(chamber.connections)

    # 9. MARKER pass: only if L0 Sanctum. Otherwise skip.
    if chamber.id == 'sanctum':
        place_sanctum_markers()

    # 10. verify_chamber_fit()  (§19.5.5)
    assert_no_duplicate_ids()
    assert_density_in_range(0.22, 0.45)
    assert_wall_coverage_in_range(0.25, 0.90)
    return tilegrid
```

Placement order is load-bearing: STRUCTURE first so walls exist to
attach to, MONUMENTAL second so the centre is reserved, STORAGE wall
third so papyri don't land on corner pillars, STORAGE floor fourth,
MARKER/OSTRAKA last.

---

## SIZING FORMULA (§19.5 Rule 3)

```python
PART_FOOTPRINT = {
    # STRUCTURE (counted only for interior pillars)
    'pillar': 3,            # 1×3
    # STORAGE
    'papyrus_tablet': 3,    # 1×3 on wall
    'wall_inscription': 6,  # 6×1 avg
    'scroll_pedestal': 2,   # 1×2
    'shelf_niche': 2,
    'rack_vertical': 3,
    'false_door': 6,        # 2×3
    'tomb_alcove': 6,       # 3×2
    'ostrakon': 1,
    # MONUMENTAL
    'stele': 3,
    'coffin': 6,
    'sculpture': 6,
    'vessel': 2,
    'rock_cut': 9,          # avg 3×3
}

PACKING_DENSITY = 0.28      # parts occupy ~28% of floor

def size_room_for(composition: dict[str, int]) -> tuple[int, int]:
    footprint = sum(PART_FOOTPRINT[p] * n for p, n in composition.items())
    floor_tiles = footprint / PACKING_DENSITY
    aspect = compute_aspect(composition)   # wall-heavy → wide, floor-heavy → square
    w = round((floor_tiles * aspect) ** 0.5)
    h = round((floor_tiles / aspect) ** 0.5)
    return clamp(w, 12, 64), clamp(h, 8, 44)
```

- **3-text chamber** → footprint ≈ 6-18 → floor ≈ 22-65 tiles →
  ~6×4 to ~8×8 → intimate, almost claustrophobic.
- **15-text chamber** → footprint ≈ 45-90 → floor ≈ 160-320 →
  ~15×12 to ~18×18 → comfortable.
- **40-text chamber** → footprint ≈ 120-240 → floor ≈ 430-860 →
  ~24×18 to ~32×26 → vast.
- **Clamped at 64×44** → a text-dense chamber fills the clamp; the
  overflow becomes wall-packed density (coverage approaches 0.90).

The user **feels** corpus density through dimension.

---

## STYLE COLUMN — WHICH BOX-SET PER HALL

The hall style (selected in the builder from the top lemma cluster)
determines the STRUCTURE glyph set:

| Hall archetype     | Style key   | Corners                | Inner   |
|--------------------|-------------|------------------------|---------|
| Oracle / Sanctum   | `oracle`    | `╔ ╗ ╚ ╝` heavy double | `·`     |
| Utterance / Logos  | `utterance` | `┌ ┐ └ ┘` light        | `·`     |
| Body / Medicine    | `body`      | `╒ ╕ ╘ ╛` mixed        | `.`     |
| Dead / Mortuary    | `dead`      | `╓ ╖ ╙ ╜` mixed inv.   | `░`     |
| Power / Royal      | `power`     | `╔ ╗ ╚ ╝` heavy double | `▒`     |
| Cosmos / Creation  | `cosmos`    | `╭ ╮ ╰ ╯` rounded      | `*`     |
| Wisdom / Scribal   | `wisdom`    | `▛ ▜ ▙ ▟` block        | `·`     |

Builder emits `chamber.hall_style` and the assembler picks.

---

## VERIFIER CHECKS (§19.5.5)

```python
def verify_chamber_fit(chamber, tilegrid):
    # Rule 2 — no canonical_id twice
    ids = [t.canonical_id for t in tilegrid.parts if t.canonical_id]
    assert len(ids) == len(set(ids))

    # Rule 4 — every text-bearing tile has a canonical_id
    for t in tilegrid.parts:
        if t.role in TEXT_BEARING_ROLES:
            assert t.canonical_id, f"{t.role} missing canonical_id"

    # Rule 3 — density in band
    parts_area = sum(PART_FOOTPRINT[t.role] for t in tilegrid.parts)
    floor_area = tilegrid.w * tilegrid.h
    assert 0.22 <= parts_area / floor_area <= 0.45

    # Wall coverage — informative, not rejected on its own
    coverage = count_wall_attached(tilegrid) / tilegrid.perimeter
    assert 0.10 <= coverage <= 0.95   # only reject on extremes
```

`TEXT_BEARING_ROLES = STORAGE ∪ MONUMENTAL`. STRUCTURE, CIRCULATION,
MARKER (non-Sanctum) may or may not carry text; not required.

---

## WHAT THIS REPLACES

- v3.1 `game.js` `setTile({ ch, fg, walk })` called ad-hoc everywhere.
- v3.1 chamber generator that pads walls with random `HIERO_SIMPLE[i]`
  glyphs — that was **filler** (§19.5 Rule 4 violation).

After v4.0, every `ch` placed in a chamber traces back to either a
STRUCTURE element (shell), a CIRCULATION element (movement), a STORAGE
or MONUMENTAL element (one canonical_id), or a Sanctum-only MARKER.

---

## IMPLEMENTATION FILES

```
web/kit/
  index.js                exports PART_FOOTPRINT, ROLE_TABLE, HALL_STYLES
  structure.js            walls, pillars, plinths, architraves
  circulation.js          floor, walkway, gateways, stairs, corridors
  storage.js              papyrus, wall_inscription, pedestal, niche,
                          rack, false_door, tomb_alcove, ostrakon
  monumental.js           stele, coffin, sculpture, vessel, rock_cut
  marker.js               torch, brazier, cartouche, scatter_glyph, sign

  assembler.js            assembleChamber() — the 10-step contract above
  verify.js               verify_chamber_fit() + the three assertions

graph/kit.py              Python-side mirror — same constants for builder
                          (PART_FOOTPRINT, ROLE_TABLE, text_type_to_part)
```

Python and JS stay in sync by single-source-of-truth JSON:

```
web/kit/kit.json          exported from graph/kit.py; web/kit/index.js
                          imports it. Never edit twice.
```

---

*A library is not a museum. Every shelf holds a book. Every book has*
*one shelf. The shape of the stacks is the shape of the collection.*
