"""Live topology engine — the corpus IS the map.

Three tiers:

  1. Levels  — stable; mined from `texts.period_label` at first request.
               One entry per L0..L7 plus per-level text count.

  2. Halls   — per level; Louvain clustering on per-level lemma
               co-occurrence. Cached after first call. Each hall has a
               defining-lemma signature that becomes its chamber_id.

  3. Chamber texts — live SQL; returns sentences whose texts carry the
               hall's defining lemmata, scoped to the level's labels.

No JSON on disk. No pre-generation. The map is a projection of the
corpus at query time.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass, asdict, field
from typing import Any

import networkx as nx
try:
    import community as community_louvain  # python-louvain
except ImportError:  # graceful fall-back
    community_louvain = None

from inference.tools._db import get_conn, put_conn
from graph.era_map import LEVELS, LEVEL_BY_ID, labels_for_level, map_label

log = logging.getLogger(__name__)


# ── Tunables ─────────────────────────────────────────────────────────────
# v5.2 INFINITY PASS — thresholds lowered so halls claim most of the corpus,
# not just the small "strong" intersection. A text joining a hall on a single
# shared signature lemma is still meaningful — that lemma IS the hall.
HALL_MIN_TEXTS = 20          # below this, a community folds into "miscellany"
MIN_LEMMA_FREQ_PER_LEVEL = 20  # only cluster lemmata with ≥N occurrences in this level
MAX_LEMMA_FRACTION = 0.25    # exclude super-common lemmata (top stopwords per level)
TOP_LEMMATA_PER_LEVEL = 500  # cap, keeps the co-occurrence graph small
EDGE_MIN_SHARED = 3          # lemmata must share ≥N sentences in this level to connect
ASSIGN_MATCH_MIN = 1         # a text joins a hall iff ≥N of its top lemmata are in the hall's signature
DEEP_ARCHIVE_MIN_TEXTS = 40  # if there are at least this many unassigned texts, emit a DEEP ARCHIVE hall instead of dropping them

# Lemmata that appear in a very high fraction of this-level sentences carry no
# clustering signal — they bind every community to every other. Excluded up
# front from the candidate set. Matches things like n.j ("belonging to"),
# ḏd ("to say"), jri̯ ("to do"), rḏi̯ ("to give"), ꜥnḫ-wḏꜣ-snb (formulaic
# epithet), etc.

# Lemmata that slip past POS filtering but carry no semantic content (or
# are so formulaic that they fire in every Egyptian text). Keyed by surface
# form; applied during candidate selection below.
GLOBAL_LEMMA_STOPFORMS: frozenset[str] = frozenset({
    "1...n",       # [cardinal number placeholder]
    "n.j",         # nisbe "belonging to"
    "nb",          # "every; all" OR homophone "lord" — both too formulaic
    "jm.j",        # nisbe "being in"
    "\u1e0fd-mdw",      # "to be pronounced" — ritual rubric head
    "\ua725",           # "portion; piece" — offering-list filler
    "\ua725n\u1e2b-w\u1e0f\ua723-snb",  # "living, prosperous, healthy" — royal epithet
    "jri\u032f",         # "to do; to make" — most frequent verb
    "r\u1e0fi\u032f",         # "to give" — second most frequent verb
    "\u1e0fd",          # "to say; to tell" — speech verb
    "jwi\u032f",         # "to come; return"
    "\u1e2b\u1e3c",          # "thousand" (offering list)
    "m\u0294\u0254",          # "see"
})

# POS prefixes to keep as clustering candidates. The corpus is full of
# pronouns, prepositions, particles, and roots that would otherwise dominate
# every community and make every hall look like "chamber of (he, the, in)".
# We want content words — nouns, verbs, adjectives, divine/place/artifact
# names, and epithets.
_POS_ALLOW_PREFIXES: tuple[str, ...] = (
    "substantive",
    "verb",
    "adjective",
    "adverb",
    "numeral",
)
_POS_ALLOW_EXACT: frozenset[str] = frozenset({
    "entity_name/gods_name",
    "entity_name/place_name",
    "entity_name/artifact_name",
    "epitheton_title/epith_god",
    "epitheton_title/title",
})


def _pos_is_contentful(pos: str | None) -> bool:
    if not pos:
        return False
    p = pos.strip()
    if p in _POS_ALLOW_EXACT:
        return True
    head = p.split("/", 1)[0]
    return head in _POS_ALLOW_PREFIXES


# ── Dataclasses ──────────────────────────────────────────────────────────
@dataclass
class LevelInfo:
    id: int
    key: str
    name_en: str
    name_de: str
    date_range: str
    blurb: str
    text_count: int
    period_labels: list[str]


@dataclass
class LemmaRef:
    id: str
    form: str
    gloss_en: str
    gloss_de: str


@dataclass
class Hall:
    chamber_id: str          # used for routing, e.g. "L1-ns-r"
    level_id: int
    name_en: str             # "CHAMBER OF NS · R" — from signature lemmata
    defining_lemmata: list[LemmaRef]   # 1-5 top lemmata (community hubs)
    text_count: int
    top_text_ids: list[str]  # preview for the minimap; full list is on-demand


# ── Module-level caches ──────────────────────────────────────────────────
_level_cache_lock = threading.Lock()
_level_cache: list[LevelInfo] | None = None

_hall_cache_lock = threading.Lock()
_hall_cache: dict[int, list[Hall]] = {}        # level_id → halls
_lemma_info_cache: dict[str, LemmaRef] = {}    # lemma_id → LemmaRef
_chamber_index: dict[str, Hall] = {}           # chamber_id → Hall (global)
_composition_cache: dict[str, dict] = {}       # chamber_id → {composition, assigned_ids}


# ── Utilities ────────────────────────────────────────────────────────────
def _slug(form: str) -> str:
    """Strip Egyptological diacritics to produce a URL-safe slug."""
    s = form or ""
    # drop anything outside [A-Za-z0-9-], keep tight
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s or "unk"


def _hydrate_lemma(lemma_id: str) -> LemmaRef:
    ref = _lemma_info_cache.get(lemma_id)
    if ref is not None:
        return ref
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, form, translation FROM lemmata WHERE id = %s",
            (lemma_id,),
        )
        row = cur.fetchone()
    finally:
        put_conn(conn)
    if not row:
        ref = LemmaRef(id=lemma_id, form=lemma_id, gloss_en="", gloss_de="")
    else:
        _, form, trans = row
        trans = trans or {}
        ref = LemmaRef(
            id=lemma_id,
            form=form or lemma_id,
            gloss_en=(trans.get("en") or "").strip(),
            gloss_de=(trans.get("de") or "").strip(),
        )
    _lemma_info_cache[lemma_id] = ref
    return ref


# ── Tier 1: Levels ───────────────────────────────────────────────────────
def level_index() -> list[LevelInfo]:
    """Enumerate levels with per-level text counts. Cached at module scope."""
    global _level_cache
    if _level_cache is not None:
        return _level_cache
    with _level_cache_lock:
        if _level_cache is not None:
            return _level_cache

        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT period_label, COUNT(*) FROM texts "
                "WHERE period_label IS NOT NULL AND period_label <> '' "
                "GROUP BY period_label"
            )
            rows = cur.fetchall()
        finally:
            put_conn(conn)

        all_labels = [r[0] for r in rows]
        count_by_label = {r[0]: int(r[1]) for r in rows}

        out: list[LevelInfo] = []
        for L in LEVELS:
            labs = labels_for_level(all_labels, L.id)
            total = sum(count_by_label.get(l, 0) for l in labs)
            out.append(LevelInfo(
                id=L.id, key=L.key, name_en=L.name_en, name_de=L.name_de,
                date_range=L.date_range, blurb=L.blurb,
                text_count=total if L.id > 0 else 9,  # L0 sanctum fixed
                period_labels=sorted(labs),
            ))
        _level_cache = out
        return _level_cache


# ── Tier 2: Halls ────────────────────────────────────────────────────────
def _fetch_lemma_sentence_pairs(period_labels: list[str]) -> list[tuple[str, int, str]]:
    """Return (lemma_id, sentence_id, canonical_id) for this level.
    Filtered to content-bearing POS categories."""
    if not period_labels:
        return []
    conn = get_conn()
    try:
        cur = conn.cursor()
        # Build POS filter: substantive%, verb%, adjective%, adverb%, numeral%,
        # plus a discrete list of allowed entity_name and epitheton_title kinds.
        cur.execute(
            """
            SELECT rli.lemma_id, rli.sentence_id, s.canonical_id
            FROM rosetta_lemma_index rli
            JOIN sentences s ON s.id = rli.sentence_id
            JOIN texts t ON t.canonical_id = s.canonical_id
            JOIN lemmata l ON l.id = rli.lemma_id
            WHERE t.period_label = ANY(%s)
              AND (
                   l.pos LIKE 'substantive%%'
                OR l.pos LIKE 'verb%%'
                OR l.pos LIKE 'adjective%%'
                OR l.pos LIKE 'adverb%%'
                OR l.pos LIKE 'numeral%%'
                OR l.pos IN (
                      'entity_name/gods_name',
                      'entity_name/place_name',
                      'entity_name/artifact_name',
                      'epitheton_title/epith_god',
                      'epitheton_title/title'
                )
              )
            """,
            (period_labels,),
        )
        return cur.fetchall()
    finally:
        put_conn(conn)


def _build_halls_for_level(level_id: int, period_labels: list[str]) -> list[Hall]:
    """The heavy lifting. Run once per level per server lifetime."""
    if community_louvain is None:
        log.error("python-louvain not installed; cannot cluster")
        return []

    t0 = time.time()
    pairs = _fetch_lemma_sentence_pairs(period_labels)
    if not pairs:
        log.info("level %d: no lemma occurrences found", level_id)
        return []

    # Lemma frequency in this level (per sentence).
    freq: dict[str, int] = {}
    text_lemmata: dict[str, set[str]] = {}  # canonical_id → set of lemma_ids
    lemma_sents: dict[str, set[int]] = {}   # lemma_id → set of sentence_ids
    all_sents: set[int] = set()

    for lemma_id, sent_id, cid in pairs:
        freq[lemma_id] = freq.get(lemma_id, 0) + 1
        text_lemmata.setdefault(cid, set()).add(lemma_id)
        lemma_sents.setdefault(lemma_id, set()).add(sent_id)
        all_sents.add(sent_id)

    total_sents = max(1, len(all_sents))

    # Adaptive thresholds: on sparse levels (<500 texts), the global floor of
    # MIN_LEMMA_FREQ_PER_LEVEL=20 kills all clustering candidates, and
    # HALL_MIN_TEXTS=30 folds every community into miscellany. Scale them down.
    n_texts = len(text_lemmata)
    # Adaptive thresholds — sparse levels need much lower bars or Louvain
    # finds nothing. Scale linearly so every era feels architecturally rich.
    #
    # L1 (20k texts): freq≥20, hall≥20, edge≥3  — original values
    # L5 (3k texts):  freq≥10, hall≥10, edge≥2
    # L2 (315 texts): freq≥2,  hall≥3,  edge≥1  — very permissive
    min_lemma_freq  = max(2, min(MIN_LEMMA_FREQ_PER_LEVEL, n_texts // 300))
    hall_min_texts  = max(3, min(HALL_MIN_TEXTS, n_texts // 25))
    edge_min_shared = max(1, min(EDGE_MIN_SHARED, n_texts // 600))

    # Hydrate forms for the blacklist check.
    floor_candidates = [lid for lid, n in freq.items() if n >= min_lemma_freq]
    forms_by_id: dict[str, str] = {}
    if floor_candidates:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, form FROM lemmata WHERE id = ANY(%s)",
                (floor_candidates,),
            )
            forms_by_id = {lid: (form or "") for lid, form in cur.fetchall()}
        finally:
            put_conn(conn)

    # Keep only contentful lemmata: above freq floor, below stopword ceiling,
    # not globally blacklisted (by form), not blacklisted (by id).
    candidates = []
    for lid in floor_candidates:
        if forms_by_id.get(lid, "") in GLOBAL_LEMMA_STOPFORMS:
            continue
        # lemma appears in > MAX_LEMMA_FRACTION of sentences → stopword-like
        if len(lemma_sents[lid]) / total_sents > MAX_LEMMA_FRACTION:
            continue
        candidates.append(lid)
    candidates.sort(key=lambda l: -freq[l])
    candidates = candidates[:TOP_LEMMATA_PER_LEVEL]
    cand_set = set(candidates)

    log.info(
        "level %d: %d texts, %d lemma-sentence edges; %d candidate lemmata (≥%d freq), hall_min=%d",
        level_id, n_texts, len(pairs), len(candidates), min_lemma_freq, hall_min_texts,
    )

    # Build lemma-lemma co-occurrence graph restricted to candidates.
    # Two lemmata connect if they co-occur in ≥EDGE_MIN_SHARED sentences.
    sent_lemmata: dict[int, list[str]] = {}
    for lid in candidates:
        for sid in lemma_sents[lid]:
            sent_lemmata.setdefault(sid, []).append(lid)

    edge_weights: dict[tuple[str, str], int] = {}
    for sid, lids in sent_lemmata.items():
        if len(lids) < 2:
            continue
        lids_sorted = sorted(lids)
        for i in range(len(lids_sorted)):
            a = lids_sorted[i]
            for j in range(i + 1, len(lids_sorted)):
                b = lids_sorted[j]
                key = (a, b)
                edge_weights[key] = edge_weights.get(key, 0) + 1

    G = nx.Graph()
    for lid in candidates:
        G.add_node(lid, weight=freq[lid])
    for (a, b), w in edge_weights.items():
        if w >= edge_min_shared:
            G.add_edge(a, b, weight=w)

    log.info("level %d: lemma graph %d nodes, %d edges; clustering…",
             level_id, G.number_of_nodes(), G.number_of_edges())

    if G.number_of_edges() == 0:
        log.info("level %d: no edges; emitting single miscellany hall", level_id)
        partition = {n: 0 for n in G.nodes()}
    else:
        partition = community_louvain.best_partition(G, random_state=42)

    # Gather communities
    communities: dict[int, list[str]] = {}
    for lid, comm in partition.items():
        communities.setdefault(comm, []).append(lid)

    # Rank each community's signature lemmata by in-community strength.
    # Louvain doesn't give us within-community edge density per node directly,
    # so we use degree-within-community as a cheap proxy: how connected the
    # lemma is to other community members, weighted by edge weight. A hub
    # that fires with many community-mates is a better name than one with
    # just raw frequency.
    import math
    N_sents = total_sents

    comm_members = {c: set(lids) for c, lids in communities.items()}

    def strength_in_comm(lid: str, comm_set: set[str]) -> float:
        total = 0.0
        if lid not in G:
            return 0.0
        for nbr, ed in G[lid].items():
            if nbr in comm_set:
                total += ed.get("weight", 1)
        # Down-weight high-freq lemmata (they are hubs everywhere).
        f = max(1, freq[lid])
        return total * math.log(1 + N_sents / f)

    hubs_for_comm: dict[int, list[str]] = {}
    for comm, lids in communities.items():
        members = comm_members[comm]
        lids.sort(key=lambda l: -strength_in_comm(l, members))
        hubs_for_comm[comm] = lids[:5]  # top-5 signature lemmata

    # Assign texts to communities by signature overlap.
    # Each text joins the community with the highest number of signature
    # lemmata present in the text's lemma set (tie-break by community size).
    sig_set_by_comm = {c: set(hubs_for_comm[c]) for c in communities}
    text_to_comm: dict[str, int | None] = {}
    for cid, lset in text_lemmata.items():
        best_comm = None
        best_score = ASSIGN_MATCH_MIN - 1  # need to beat this
        for comm, sig in sig_set_by_comm.items():
            score = len(lset & sig)
            if score > best_score:
                best_score = score
                best_comm = comm
            elif score == best_score and best_comm is not None:
                # Tie-break: prefer larger community (more common words)
                if len(communities[comm]) > len(communities[best_comm]):
                    best_comm = comm
        text_to_comm[cid] = best_comm

    texts_by_comm: dict[int, list[str]] = {}
    for cid, comm in text_to_comm.items():
        if comm is None:
            continue
        texts_by_comm.setdefault(comm, []).append(cid)

    # Emit halls: size threshold; smaller communities fold into miscellany
    halls: list[Hall] = []
    misc_texts: list[str] = []
    misc_sigs: list[str] = []
    for comm, lids in communities.items():
        cids = texts_by_comm.get(comm, [])
        if len(cids) < hall_min_texts:
            misc_texts.extend(cids)
            misc_sigs.extend(hubs_for_comm[comm][:2])
            continue
        signature = [_hydrate_lemma(l) for l in hubs_for_comm[comm]]
        chamber_id = _make_chamber_id(level_id, signature)
        name = _make_chamber_name(signature)
        halls.append(Hall(
            chamber_id=chamber_id,
            level_id=level_id,
            name_en=name,
            defining_lemmata=signature,
            text_count=len(cids),
            top_text_ids=cids[:8],
        ))

    # Sort halls by size desc, dedupe chamber_ids (collisions mean same hub)
    halls.sort(key=lambda h: -h.text_count)
    seen_ids: set[str] = set()
    uniq: list[Hall] = []
    for h in halls:
        base = h.chamber_id
        n = 1
        while h.chamber_id in seen_ids:
            n += 1
            h.chamber_id = f"{base}-{n}"
        seen_ids.add(h.chamber_id)
        uniq.append(h)

    if len(misc_texts) >= hall_min_texts:
        # Build a miscellany signature from top-frequency lemmata found in misc
        # communities. Using misc_sigs collected above.
        misc_freq: dict[str, int] = {}
        for l in misc_sigs:
            misc_freq[l] = misc_freq.get(l, 0) + 1
        top = sorted(misc_freq, key=lambda l: -misc_freq[l])[:3]
        sig = [_hydrate_lemma(l) for l in top] if top else []
        name = "HALL OF THE MISCELLANY" if not sig else (
            "HALL OF " + " · ".join(
                (lr.gloss_en or lr.form).upper().split(",")[0][:20] for lr in sig
            )
        )
        chamber_id = f"L{level_id}-misc"
        uniq.append(Hall(
            chamber_id=chamber_id,
            level_id=level_id,
            name_en=name,
            defining_lemmata=sig,
            text_count=len(misc_texts),
            top_text_ids=misc_texts[:8],
        ))

    # v5.2 DEEP ARCHIVE — every text in this level that still has no hall
    # lands here. The library is infinite; nothing is forgotten. Unassigned
    # texts include those with no candidate lemmata in common with any
    # community, plus anything the assignment pass dropped.
    assigned_all: set[str] = set()
    for h in uniq:
        # top_text_ids is only the preview; the full bucket lives in
        # texts_by_comm before miscellany collapse. We'll rebuild below.
        pass
    # Walk text_to_comm: every text whose comm is None OR whose comm folded
    # into misc *already* in misc_texts; every text with comm but that comm
    # didn't ship (in misc_texts). So the truly-unassigned set is:
    all_level_texts = set(text_lemmata.keys())
    accounted = set(misc_texts)
    for comm, lids in communities.items():
        cids = texts_by_comm.get(comm, [])
        if len(cids) >= hall_min_texts:
            accounted.update(cids)
    # Also any text whose comm is None (no signature overlap) is pure unassigned
    for cid, comm in text_to_comm.items():
        if comm is None:
            pass  # falls through — will be picked up as unassigned below
    unassigned = sorted(all_level_texts - accounted)
    if len(unassigned) >= DEEP_ARCHIVE_MIN_TEXTS:
        uniq.append(Hall(
            chamber_id=f"L{level_id}-archive",
            level_id=level_id,
            name_en=f"DEEP ARCHIVE · L{level_id}",
            defining_lemmata=[],
            text_count=len(unassigned),
            top_text_ids=unassigned[:8],
        ))
        # Stash the full list so /chamber/{id}/texts can serve it.
        _composition_cache[f"L{level_id}-archive"] = {
            "composition": {},
            "assigned_ids": unassigned,
        }
        log.info("level %d: DEEP ARCHIVE with %d unassigned texts",
                 level_id, len(unassigned))

    elapsed = time.time() - t0
    log.info("level %d: built %d halls in %.1fs (incl. miscellany: %d, archive: %d)",
             level_id, len(uniq), elapsed,
             1 if len(misc_texts) >= HALL_MIN_TEXTS else 0,
             1 if len(unassigned) >= DEEP_ARCHIVE_MIN_TEXTS else 0)

    # Register in chamber_index for cross-level lookup
    for h in uniq:
        _chamber_index[h.chamber_id] = h

    return uniq


def _make_chamber_id(level_id: int, signature: list[LemmaRef]) -> str:
    parts = [_slug(s.form) for s in signature[:2]]
    core = "-".join(p for p in parts if p) or "unk"
    return f"L{level_id}-{core}"


def _make_chamber_name(signature: list[LemmaRef]) -> str:
    if not signature:
        return "CHAMBER (unnamed)"
    glosses: list[str] = []
    for lr in signature[:3]:
        g = (lr.gloss_en or lr.form).split(",")[0].split(";")[0].strip()
        # Prefer shortest distinct gloss
        g = g.split("/")[0].strip()
        if g:
            glosses.append(g.upper()[:24])
    if not glosses:
        return f"CHAMBER OF {signature[0].form.upper()}"
    return "CHAMBER OF " + " · ".join(glosses)


def halls_for_level(level_id: int) -> list[Hall]:
    """Return halls for a level. Cached after first call."""
    if level_id == 0:
        return []  # Sanctum is hand-authored in the frontend
    if level_id in _hall_cache:
        return _hall_cache[level_id]
    with _hall_cache_lock:
        if level_id in _hall_cache:
            return _hall_cache[level_id]
        info = LEVEL_BY_ID.get(level_id)
        if info is None:
            return []
        levels = level_index()
        period_labels = next((L.period_labels for L in levels if L.id == level_id), [])
        halls = _build_halls_for_level(level_id, period_labels)
        _hall_cache[level_id] = halls
        return halls


def chamber_by_id(chamber_id: str) -> Hall | None:
    """Look up a hall globally; triggers clustering for the owning level
    if not yet built. Sub-chamber IDs (suffix '::N') fall back to the
    parent hall."""
    if chamber_id in _chamber_index:
        return _chamber_index[chamber_id]
    # Sub-chamber suffix added by the frontend layout splitter: "<parent>::N".
    # The server doesn't maintain sub-chamber identity — it serves the parent.
    if "::" in chamber_id:
        parent = chamber_id.split("::", 1)[0]
        return chamber_by_id(parent)
    # chamber_id = L<n>-<slug>
    m = re.match(r"^L(\d+)-", chamber_id)
    if not m:
        return None
    lvl = int(m.group(1))
    halls_for_level(lvl)
    return _chamber_index.get(chamber_id)


# ── Tier 3: Chamber contents (live query) ────────────────────────────────
def texts_for_chamber(chamber_id: str, limit: int = 60) -> dict[str, Any]:
    """Return passages belonging to a chamber, one sentence per canonical_id.

    A text belongs to a chamber iff it carries ≥ASSIGN_MATCH_MIN of the
    chamber's defining lemmata AND its period_label maps to the chamber's
    level. Ordering: by how many signature lemmata the text hits, desc.

    Sub-chamber ids ("<parent>::N") resolve to the parent hall's passages.
    """
    # Sub-chamber routing — share the parent's passage pool.
    if "::" in chamber_id:
        parent = chamber_id.split("::", 1)[0]
        return texts_for_chamber(parent, limit)

    hall = chamber_by_id(chamber_id)
    if hall is None:
        return {"chamber_id": chamber_id, "error": "not found"}

    sig_ids = [lr.id for lr in hall.defining_lemmata]
    if not sig_ids:
        # DEEP ARCHIVE has no signature lemmata — serve passages direct
        # from the cached assigned_ids list (the true unassigned texts).
        cached = _composition_cache.get(chamber_id)
        if cached and cached.get("assigned_ids"):
            return _texts_by_ids(chamber_id, hall, cached["assigned_ids"], limit)
        return {
            "chamber_id": chamber_id, "name_en": hall.name_en,
            "level_id": hall.level_id, "passages": [], "total": 0,
        }

    levels = level_index()
    period_labels = next(
        (L.period_labels for L in levels if L.id == hall.level_id), []
    )
    if not period_labels:
        return {
            "chamber_id": chamber_id, "name_en": hall.name_en,
            "level_id": hall.level_id, "passages": [], "total": 0,
        }

    conn = get_conn()
    try:
        cur = conn.cursor()
        # Select best sentence per canonical_id (longest English translation),
        # ranked by how many signature lemmata the text carries.
        cur.execute(
            """
            WITH text_scores AS (
                SELECT DISTINCT s.canonical_id,
                       COUNT(DISTINCT rli.lemma_id) AS sig_hits
                FROM sentences s
                JOIN texts t ON t.canonical_id = s.canonical_id
                JOIN rosetta_lemma_index rli ON rli.sentence_id = s.id
                WHERE t.period_label = ANY(%s)
                  AND rli.lemma_id = ANY(%s)
                GROUP BY s.canonical_id
                HAVING COUNT(DISTINCT rli.lemma_id) >= %s
                ORDER BY sig_hits DESC
                LIMIT %s
            ),
            ranked AS (
                SELECT s.canonical_id, s.id AS sentence_id,
                       s.transliteration, s.translation,
                       t.conventional_name, t.period_label, t.shelfmarks,
                       ts.sig_hits,
                       ROW_NUMBER() OVER (
                           PARTITION BY s.canonical_id
                           ORDER BY length(s.translation::text) DESC
                       ) AS rn
                FROM text_scores ts
                JOIN sentences s ON s.canonical_id = ts.canonical_id
                JOIN texts t ON t.canonical_id = s.canonical_id
                WHERE s.translation IS NOT NULL
                  AND length(s.translation::text) > 20
            )
            SELECT canonical_id, sentence_id, transliteration, translation,
                   conventional_name, period_label, shelfmarks, sig_hits
            FROM ranked
            WHERE rn = 1
            ORDER BY sig_hits DESC
            """,
            (period_labels, sig_ids, min(ASSIGN_MATCH_MIN, len(sig_ids)), limit),
        )
        rows = cur.fetchall()
    finally:
        put_conn(conn)

    passages = []
    for cid, sid, trans_lit, translation, name, period, shelf, hits in rows:
        trans = translation or {}
        en = trans.get("en", "") if isinstance(trans, dict) else str(trans)
        passages.append({
            "canonical_id": cid,
            "sentence_id": sid,
            "transliteration": trans_lit or "",
            "translation": en,
            "text_name": name or "",
            "period": period or "",
            "shelfmark": (shelf or [""])[0] if shelf else "",
            "sig_hits": int(hits),
        })

    return {
        "chamber_id": chamber_id,
        "name_en": hall.name_en,
        "level_id": hall.level_id,
        "defining_lemmata": [asdict(lr) for lr in hall.defining_lemmata],
        "passages": passages,
        "total": len(passages),
    }


def _texts_by_ids(chamber_id: str, hall: "Hall", ids: list[str], limit: int) -> dict[str, Any]:
    """Serve passages for a list of canonical_ids (DEEP ARCHIVE path).

    Returns the longest-translation sentence per canonical_id, capped at
    ``limit``. Unlike texts_for_chamber, there's no sig_hits ranking — the
    archive is ordered by canonical_id and truncated to the first N ids.
    """
    if not ids:
        return {
            "chamber_id": chamber_id, "name_en": hall.name_en,
            "level_id": hall.level_id, "passages": [], "total": 0,
        }
    head = ids[:max(1, int(limit))]
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            WITH ranked AS (
              SELECT s.canonical_id, s.id AS sentence_id,
                     s.transliteration, s.translation,
                     t.conventional_name, t.period_label, t.shelfmarks,
                     ROW_NUMBER() OVER (
                       PARTITION BY s.canonical_id
                       ORDER BY length(s.translation::text) DESC
                     ) AS rn
              FROM sentences s
              JOIN texts t ON t.canonical_id = s.canonical_id
              WHERE s.canonical_id = ANY(%s)
                AND s.translation IS NOT NULL
            )
            SELECT canonical_id, sentence_id, transliteration, translation,
                   conventional_name, period_label, shelfmarks
            FROM ranked WHERE rn = 1
            """,
            (head,),
        )
        rows = cur.fetchall()
    finally:
        put_conn(conn)
    passages = []
    for cid, sid, trans_lit, translation, name, period, shelf in rows:
        trans = translation or {}
        en = trans.get("en", "") if isinstance(trans, dict) else str(trans)
        passages.append({
            "canonical_id": cid,
            "sentence_id": sid,
            "transliteration": trans_lit or "",
            "translation": en,
            "text_name": name or "",
            "period": period or "",
            "shelfmark": (shelf or [""])[0] if shelf else "",
            "sig_hits": 0,
        })
    return {
        "chamber_id": chamber_id,
        "name_en": hall.name_en,
        "level_id": hall.level_id,
        "defining_lemmata": [],
        "passages": passages,
        "total": len(passages),
    }


# ── Chamber composition (for kit-of-parts assembler) ─────────────────────
def composition_for_chamber(chamber_id: str) -> dict[str, Any]:
    """Return text_type composition + full canonical_id list for a chamber.

    Kit-of-parts assembler feeds {composition, assigned_ids} into
    ``kit.size_room_for()`` and ``kit.verify_composition()``.

    Shape::

        {
          "chamber_id": str,
          "level_id":   int,
          "text_type_composition": {text_type: count, ...},
          "assigned_ids": [canonical_id, ...],  # full list, unique
          "total": int,
        }

    Cached per chamber_id. First call builds the owning level's halls
    if not already cached.
    """
    # Sub-chamber id ("<parent>::N") — serve the parent's composition. The
    # frontend already slices assigned_ids into sub-chamber buckets.
    if "::" in chamber_id:
        parent = chamber_id.split("::", 1)[0]
        return composition_for_chamber(parent)

    cached = _composition_cache.get(chamber_id)
    if cached is not None:
        # The archive chamber stores only the id list in cache; hydrate the
        # standard response shape on the fly.
        if chamber_id.endswith("-archive") and "level_id" not in cached:
            hall = chamber_by_id(chamber_id)
            out = {
                "chamber_id": chamber_id,
                "level_id": hall.level_id if hall else -1,
                "text_type_composition": cached.get("composition", {}),
                "assigned_ids": cached.get("assigned_ids", []),
                "total": len(cached.get("assigned_ids", [])),
            }
            _composition_cache[chamber_id] = out
            return out
        return cached

    hall = chamber_by_id(chamber_id)
    if hall is None:
        return {"chamber_id": chamber_id, "error": "not found"}

    sig_ids = [lr.id for lr in hall.defining_lemmata]
    if not sig_ids:
        out = {
            "chamber_id": chamber_id,
            "level_id": hall.level_id,
            "text_type_composition": {},
            "assigned_ids": [],
            "total": 0,
        }
        _composition_cache[chamber_id] = out
        return out

    levels = level_index()
    period_labels = next(
        (L.period_labels for L in levels if L.id == hall.level_id), []
    )
    if not period_labels:
        out = {
            "chamber_id": chamber_id,
            "level_id": hall.level_id,
            "text_type_composition": {},
            "assigned_ids": [],
            "total": 0,
        }
        _composition_cache[chamber_id] = out
        return out

    conn = get_conn()
    try:
        cur = conn.cursor()
        # All texts in this level that carry ≥ASSIGN_MATCH_MIN signature
        # lemmata, along with their text_type. One row per canonical_id.
        cur.execute(
            """
            SELECT t.canonical_id, COALESCE(NULLIF(t.text_type, ''), 'unknown')
            FROM texts t
            WHERE t.period_label = ANY(%s)
              AND t.canonical_id IN (
                SELECT s.canonical_id
                FROM sentences s
                JOIN rosetta_lemma_index rli ON rli.sentence_id = s.id
                WHERE rli.lemma_id = ANY(%s)
                GROUP BY s.canonical_id
                HAVING COUNT(DISTINCT rli.lemma_id) >= %s
              )
            """,
            (period_labels, sig_ids, min(ASSIGN_MATCH_MIN, len(sig_ids))),
        )
        rows = cur.fetchall()
    finally:
        put_conn(conn)

    composition: dict[str, int] = {}
    assigned_ids: list[str] = []
    for cid, tt in rows:
        tt = (tt or "unknown").strip() or "unknown"
        composition[tt] = composition.get(tt, 0) + 1
        assigned_ids.append(cid)

    out = {
        "chamber_id": chamber_id,
        "level_id": hall.level_id,
        "text_type_composition": composition,
        "assigned_ids": assigned_ids,
        "total": len(assigned_ids),
    }
    _composition_cache[chamber_id] = out
    return out


# ── Search helper for find_chamber tool ──────────────────────────────────
def find_chamber_by_concept(concept: str, level_id: int | None = None) -> list[dict]:
    """Return halls whose defining lemmata match `concept` in form or gloss.

    If level_id is None, searches all currently-cached levels. If no levels
    are yet cached, builds L1 first (the largest) so there's always at least
    one to match against.
    """
    concept_lower = (concept or "").lower().strip()
    if not concept_lower:
        return []

    # Ensure at least one level cached so we have anything to match.
    if not _hall_cache:
        halls_for_level(1)

    target_levels = (
        [level_id] if level_id is not None else sorted(_hall_cache.keys())
    )

    matches: list[tuple[int, Hall]] = []
    for lvl in target_levels:
        for h in _hall_cache.get(lvl, []):
            score = 0
            for lr in h.defining_lemmata:
                form = (lr.form or "").lower()
                glo = (lr.gloss_en or "").lower()
                glo_de = (lr.gloss_de or "").lower()
                if concept_lower == form:
                    score += 100
                elif concept_lower in form.split():
                    score += 60
                if concept_lower in glo or concept_lower in glo_de:
                    score += 40
                # word-level overlap
                words = set(concept_lower.split())
                for w in words:
                    if w and (w in glo or w in glo_de or w == form):
                        score += 10
            if score > 0:
                matches.append((score, h))

    matches.sort(key=lambda x: (-x[0], -x[1].text_count))
    out = []
    for score, h in matches[:8]:
        out.append({
            "chamber_id": h.chamber_id,
            "name_en": h.name_en,
            "level_id": h.level_id,
            "text_count": h.text_count,
            "defining_lemmata": [asdict(lr) for lr in h.defining_lemmata],
            "score": score,
        })
    return out


# ── Invalidation (for tests / tooling) ───────────────────────────────────
def reset_caches() -> None:
    global _level_cache
    with _level_cache_lock:
        _level_cache = None
    with _hall_cache_lock:
        _hall_cache.clear()
        _chamber_index.clear()
    _lemma_info_cache.clear()
    _composition_cache.clear()
