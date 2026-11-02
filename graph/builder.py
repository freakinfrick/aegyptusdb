#!/usr/bin/env python3
"""Build the chamber graph from corpus queries.

Queries PostgreSQL directly for speed. Outputs graph/chambers.json.
Run from the repo root with the venv activated:
    python graph/builder.py
"""

import json
import os
import sys
from collections import defaultdict
from itertools import combinations

import psycopg2

DB_URL = os.environ.get("DB_URL", "postgresql://aegyptus:dev@localhost:5434/aegyptus")

# ── Seed chambers: concept → search terms for translation grep ──────────────
SEED_CHAMBERS = [
    {
        "id": "tongue",
        "name_en": "CHAMBER OF THE TONGUE",
        "term_eg": "ns · rʾ",
        "term_transliteration": "ns, rʾ",
        "search_terms": ["tongue"],
        "depth": 1,
    },
    {
        "id": "heart",
        "name_en": "CHAMBER OF THE HEART",
        "term_eg": "jb · ḥꜣtj",
        "term_transliteration": "jb, ḥꜣtj",
        "search_terms": ["heart"],
        "depth": 1,
    },
    {
        "id": "spine",
        "name_en": "CHAMBER OF THE SPINE",
        "term_eg": "ḏt · ṯꜣst · ḏd",
        "term_transliteration": "ḏt, ṯꜣst, ḏd",
        "search_terms": ["spine", "backbone", "vertebra", "djed"],
        "depth": 2,
    },
    {
        "id": "word",
        "name_en": "CHAMBER OF THE WORD",
        "term_eg": "mdw · Ḥkꜣ",
        "term_transliteration": "mdw, Ḥkꜣ",
        "search_terms": ["word", "speech", "utterance", "heka", "magic word"],
        "depth": 1,
    },
    {
        "id": "eye",
        "name_en": "CHAMBER OF THE EYE",
        "term_eg": "jrt · wḏꜣt",
        "term_transliteration": "jrt, wḏꜣt",
        "search_terms": ["eye", "wedjat", "udjat"],
        "depth": 1,
    },
    {
        "id": "mouth",
        "name_en": "CHAMBER OF THE MOUTH",
        "term_eg": "rʾ · sbꜣ",
        "term_transliteration": "rʾ, sbꜣ",
        "search_terms": ["mouth", "opening of the mouth"],
        "depth": 1,
    },
    {
        "id": "temple",
        "name_en": "CHAMBER OF THE TEMPLE",
        "term_eg": "ḥwt-nṯr",
        "term_transliteration": "ḥwt-nṯr",
        "search_terms": ["temple", "sanctuary", "shrine"],
        "depth": 2,
    },
    {
        "id": "flood",
        "name_en": "CHAMBER OF THE FLOOD",
        "term_eg": "ḥʿpj",
        "term_transliteration": "ḥʿpj",
        "search_terms": ["flood", "inundation", "nile", "hapy"],
        "depth": 2,
    },
    {
        "id": "creation",
        "name_en": "CHAMBER OF CREATION",
        "term_eg": "ḫpr · bnbn",
        "term_transliteration": "ḫpr, bnbn",
        "search_terms": ["creation", "created", "come into being", "primeval"],
        "depth": 3,
    },
    {
        "id": "pillar",
        "name_en": "CHAMBER OF THE PILLAR",
        "term_eg": "jwn · ḏd",
        "term_transliteration": "jwn, ḏd",
        "search_terms": ["pillar", "column", "djed", "obelisk"],
        "depth": 3,
    },
]

# Direction assignments for corridors (layout-aware)
DIRECTION_MAP = {
    ("tongue", "heart"): ("W", "E"),
    ("tongue", "word"): ("N", "S"),
    ("tongue", "mouth"): ("E", "W"),
    ("heart", "spine"): ("S", "N"),
    ("heart", "creation"): ("SW", "NE"),
    ("spine", "pillar"): ("E", "W"),
    ("spine", "temple"): ("S", "N"),
    ("word", "creation"): ("W", "E"),
    ("word", "mouth"): ("SE", "NW"),
    ("eye", "mouth"): ("S", "N"),
    ("eye", "creation"): ("W", "E"),
    ("mouth", "temple"): ("S", "N"),
    ("temple", "pillar"): ("E", "W"),
    ("temple", "flood"): ("S", "N"),
    ("flood", "creation"): ("W", "E"),
    ("creation", "pillar"): ("S", "N"),
}


def get_connection():
    return psycopg2.connect(DB_URL)


def find_texts_for_chamber(cur, search_terms: list[str], limit: int = 30) -> list[dict]:
    """Find texts matching search terms in sentence translations."""
    conditions = " OR ".join(
        [f"s.translation::text ILIKE %s" for _ in search_terms]
    )
    params = [f"%{term}%" for term in search_terms]

    cur.execute(f"""
        SELECT DISTINCT s.canonical_id, s.transliteration, s.translation,
               t.conventional_name, t.period_label, t.current_location,
               t.shelfmarks, t.date_earliest, t.date_latest
        FROM sentences s
        JOIN texts t ON t.canonical_id = s.canonical_id
        WHERE ({conditions})
          AND s.translation IS NOT NULL
          AND s.translation::text != 'null'
        ORDER BY s.canonical_id
        LIMIT %s
    """, params + [limit])

    results = []
    seen_ids = set()
    for row in cur.fetchall():
        cid = row[0]
        if cid in seen_ids:
            continue
        seen_ids.add(cid)
        trans = row[2]
        en = ""
        if isinstance(trans, dict):
            en = trans.get("en", trans.get("de", ""))
        elif isinstance(trans, str):
            en = trans

        results.append({
            "canonical_id": cid,
            "transliteration": row[1] or "",
            "translation_en": en,
            "conventional_name": row[3] or "",
            "period_label": row[4] or "",
            "current_location": row[5] or "",
            "shelfmarks": row[6] or [],
            "date_earliest": row[7],
            "date_latest": row[8],
        })
    return results


def get_highlight_quotes(cur, canonical_ids: list[str], search_terms: list[str], limit: int = 3) -> list[dict]:
    """Get the best quotes from the chamber's texts."""
    if not canonical_ids:
        return []

    placeholders = ",".join(["%s"] * len(canonical_ids))
    conditions = " OR ".join(
        [f"s.translation::text ILIKE %s" for _ in search_terms]
    )
    term_params = [f"%{term}%" for term in search_terms]

    cur.execute(f"""
        SELECT s.canonical_id, s.transliteration, s.translation,
               t.conventional_name, t.period_label, t.shelfmarks
        FROM sentences s
        JOIN texts t ON t.canonical_id = s.canonical_id
        WHERE s.canonical_id IN ({placeholders})
          AND ({conditions})
          AND s.translation IS NOT NULL
          AND length(s.translation::text) > 40
          AND length(s.translation::text) < 500
        ORDER BY length(s.translation::text) DESC
        LIMIT %s
    """, canonical_ids + term_params + [limit * 3])

    quotes = []
    for row in cur.fetchall():
        trans = row[2]
        en = ""
        if isinstance(trans, dict):
            en = trans.get("en", trans.get("de", ""))
        elif isinstance(trans, str):
            en = trans

        if len(en) < 30:
            continue

        shelfmarks = row[5] or []
        shelfmark = shelfmarks[0] if shelfmarks else ""

        quotes.append({
            "quote": en.strip(),
            "transliteration": (row[1] or "")[:200],
            "canonical_id": row[0],
            "shelfmark": shelfmark,
            "period": row[4] or "",
            "text_name": row[3] or "",
        })

    # Deduplicate by canonical_id and take best
    seen = set()
    deduped = []
    for q in quotes:
        if q["canonical_id"] not in seen:
            seen.add(q["canonical_id"])
            deduped.append(q)
    return deduped[:limit]


def get_hieroglyphic(cur, canonical_id: str) -> str:
    """Get hieroglyphic layer for a text if available."""
    cur.execute("""
        SELECT content FROM representation_layers
        WHERE canonical_id = %s AND layer_type = 'hieroglyphic'
        LIMIT 1
    """, (canonical_id,))
    row = cur.fetchone()
    if row and row[0]:
        content = row[0]
        if isinstance(content, dict):
            return content.get("text", content.get("content", ""))
        return str(content)[:200]
    return ""


def compute_period_range(texts: list[dict]) -> str:
    """Compute human-readable period range from text dates."""
    periods = [t["period_label"] for t in texts if t.get("period_label")]
    if not periods:
        return "Unknown"

    # Use earliest/latest dates
    earliests = [t["date_earliest"] for t in texts if t.get("date_earliest")]
    latests = [t["date_latest"] for t in texts if t.get("date_latest")]

    if earliests and latests:
        e = min(earliests)
        l = max(latests)
        if e < 0 and l < 0:
            return f"{abs(e)} BCE – {abs(l)} BCE"
        elif e < 0:
            return f"{abs(e)} BCE – {l} CE"
        else:
            return f"{e} CE – {l} CE"

    # Fallback: use period labels
    unique = list(dict.fromkeys(periods))
    if len(unique) <= 3:
        return " – ".join(unique)
    return f"{unique[0]} – {unique[-1]}"


def build_corridors(chambers: list[dict]) -> None:
    """Compute corridors between chambers based on shared texts."""
    id_to_chamber = {c["id"]: c for c in chambers}

    for (a_id, b_id), (dir_a, dir_b) in DIRECTION_MAP.items():
        a = id_to_chamber.get(a_id)
        b = id_to_chamber.get(b_id)
        if not a or not b:
            continue

        shared = set(a["canonical_ids"]) & set(b["canonical_ids"])
        strength = len(shared)

        # Always connect mapped chambers, even without shared texts
        if strength == 0:
            strength = 1  # conceptual connection

        a_label = f"{b['term_eg']} · {b['id']}"
        b_label = f"{a['term_eg']} · {a['id']}"

        a["corridors"].append({
            "target_id": b_id,
            "label": a_label,
            "strength": strength,
            "direction": dir_a,
        })
        b["corridors"].append({
            "target_id": a_id,
            "label": b_label,
            "strength": strength,
            "direction": dir_b,
        })

    # Also find additional connections via shared texts (not in map)
    for a, b in combinations(chambers, 2):
        pair = (a["id"], b["id"])
        pair_r = (b["id"], a["id"])
        if pair in DIRECTION_MAP or pair_r in DIRECTION_MAP:
            continue

        shared = set(a["canonical_ids"]) & set(b["canonical_ids"])
        if len(shared) >= 3:
            # Auto-assign directions
            used_dirs_a = {c["direction"] for c in a["corridors"]}
            used_dirs_b = {c["direction"] for c in b["corridors"]}
            all_dirs = ["N", "S", "E", "W", "NE", "NW", "SE", "SW"]
            dir_a = next((d for d in all_dirs if d not in used_dirs_a), "N")
            opp = {"N": "S", "S": "N", "E": "W", "W": "E",
                   "NE": "SW", "SW": "NE", "NW": "SE", "SE": "NW"}
            dir_b = opp.get(dir_a, "S")

            a["corridors"].append({
                "target_id": b["id"],
                "label": f"{b['term_eg']} · {b['id']}",
                "strength": len(shared),
                "direction": dir_a,
            })
            b["corridors"].append({
                "target_id": a["id"],
                "label": f"{a['term_eg']} · {a['id']}",
                "strength": len(shared),
                "direction": dir_b,
            })


def build():
    """Main builder: query corpus, build chambers, compute corridors, output JSON."""
    conn = get_connection()
    cur = conn.cursor()
    chambers = []

    for seed in SEED_CHAMBERS:
        print(f"Building {seed['id']}...", end=" ", flush=True)

        # Find texts
        texts = find_texts_for_chamber(cur, seed["search_terms"], limit=40)
        canonical_ids = [t["canonical_id"] for t in texts]
        print(f"{len(canonical_ids)} texts", end=" ", flush=True)

        # Get highlight quotes
        quotes = get_highlight_quotes(cur, canonical_ids, seed["search_terms"])
        print(f"{len(quotes)} quotes", end=" ", flush=True)

        # Period range
        period_range = compute_period_range(texts)

        chamber = {
            "id": seed["id"],
            "name_en": seed["name_en"],
            "term_eg": seed["term_eg"],
            "term_transliteration": seed["term_transliteration"],
            "depth": seed["depth"],
            "text_count": len(canonical_ids),
            "period_range": period_range,
            "canonical_ids": canonical_ids,
            "highlight_quotes": quotes,
            "corridors": [],
            "locked": False,
        }
        chambers.append(chamber)
        print("✓")

    # Compute corridors
    print("Computing corridors...", flush=True)
    build_corridors(chambers)
    total_corridors = sum(len(c["corridors"]) for c in chambers)
    print(f"  {total_corridors} corridors total")

    # Output
    output_path = os.path.join(os.path.dirname(__file__), "chambers.json")
    with open(output_path, "w") as f:
        json.dump(chambers, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {output_path}")
    print(f"  {len(chambers)} chambers, {total_corridors} corridors")

    conn.close()


if __name__ == "__main__":
    build()
