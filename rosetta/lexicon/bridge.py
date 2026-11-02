"""GermanEnglishBridge — translate German Egyptological glosses to English."""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class GermanEnglishBridge:
    """Translate German Egyptological glosses to English via LLM or static dictionary."""

    # Static fallback: ~200 common Egyptological DE->EN pairs
    STATIC_BRIDGE: dict[str, str] = {
        "Opfer": "offering", "König": "king", "Gott": "god", "Herr": "lord",
        "Frau": "woman", "Mann": "man", "Sohn": "son", "Tochter": "daughter",
        "Wasser": "water", "Himmel": "sky", "Erde": "earth", "Berg": "mountain",
        "Haus": "house", "Tempel": "temple", "Grab": "tomb", "Palast": "palace",
        "Auge": "eye", "Herz": "heart", "Hand": "hand", "Mund": "mouth",
        "Kopf": "head", "Arm": "arm", "Bein": "leg", "Körper": "body",
        "Leben": "life", "Tod": "death", "Seele": "soul", "Name": "name",
        "Macht": "power", "Kraft": "strength", "Weisheit": "wisdom",
        "Wahrheit": "truth", "Gerechtigkeit": "justice", "Ordnung": "order",
        "Liebe": "love", "Feind": "enemy", "Freund": "friend",
        "Priester": "priest", "Schreiber": "scribe", "Diener": "servant",
        "Gold": "gold", "Silber": "silver", "Kupfer": "copper",
        "Brot": "bread", "Bier": "beer", "Wein": "wine", "Fleisch": "meat",
        "Rind": "cattle", "Vogel": "bird", "Fisch": "fish", "Schlange": "snake",
        "Löwe": "lion", "Krokodil": "crocodile", "Falke": "falcon",
        "Sonne": "sun", "Mond": "moon", "Stern": "star", "Fluss": "river",
        "See": "lake", "Meer": "sea", "Wind": "wind", "Feuer": "fire",
        "Baum": "tree", "Feld": "field", "Garten": "garden",
        "Schiff": "ship", "Weg": "path", "Tor": "gate", "Mauer": "wall",
        "Krieg": "war", "Sieg": "victory", "Heer": "army",
        "Fest": "festival", "Gebet": "prayer", "Ritual": "ritual",
        "Statue": "statue", "Stele": "stela", "Sarg": "coffin",
        "geben": "to give", "machen": "to make", "kommen": "to come",
        "gehen": "to go", "sagen": "to say", "sehen": "to see",
        "hören": "to hear", "wissen": "to know", "bringen": "to bring",
        "nehmen": "to take", "setzen": "to place", "öffnen": "to open",
        "schließen": "to close", "leben": "to live", "sterben": "to die",
        "lieben": "to love", "hassen": "to hate", "fürchten": "to fear",
        "schlagen": "to strike", "schützen": "to protect",
        "erheben": "to raise", "fallen": "to fall",
        "essen": "to eat", "trinken": "to drink",
        "groß": "great", "klein": "small", "gut": "good", "schlecht": "bad",
        "schön": "beautiful", "heilig": "sacred", "göttlich": "divine",
        "ewig": "eternal", "alt": "old", "neu": "new",
        "weiß": "white", "schwarz": "black", "rot": "red", "grün": "green",
        "alle": "all", "jeder": "every", "dieser": "this",
        "Hirt": "shepherd", "Hüter": "guardian", "Wächter": "watchman",
        "Richter": "judge", "Bote": "messenger", "Bruder": "brother",
        "Schwester": "sister", "Vater": "father", "Mutter": "mother",
        "Oberägypten": "Upper Egypt", "Unterägypten": "Lower Egypt",
        "Pyramide": "pyramid", "Obelisk": "obelisk",
        "Totenbuch": "Book of the Dead", "Spruch": "spell",
        "Inschrift": "inscription", "Papyrus": "papyrus",
        "Thron": "throne", "Krone": "crown", "Szepter": "scepter",
        "Stirn": "forehead", "Brust": "chest", "Rücken": "back",
        "Finger": "finger", "Fuß": "foot",
        "Kobra": "cobra", "Skarabäus": "scarab", "Ibis": "ibis",
        "Nilpferd": "hippopotamus", "Pavian": "baboon",
        "Nil": "Nile", "Wüste": "desert", "Oase": "oasis",
        "Norden": "north", "Süden": "south", "Osten": "east", "Westen": "west",
        "Ewigkeit": "eternity", "Unterwelt": "underworld", "Jenseits": "afterlife",
        "Schöpfung": "creation", "Entstehung": "origin",
        "Opfergabe": "offering", "Opferformel": "offering formula",
        "Titel": "title", "Rang": "rank", "Amt": "office",
        "Erbe": "heir", "Nachfolger": "successor",
        "Verklärung": "transfiguration", "Rechtfertigung": "justification",
        "Reinigung": "purification", "Salbung": "anointing",
        "Mundöffnung": "opening of the mouth",
        "Totenopfer": "funerary offering",
        "Grabbeigabe": "grave goods",
        "Sternenuhr": "star clock",
        "Sonnenlauf": "solar course",
        "Königsliste": "king list",
        "Annalen": "annals",
        "Weisheitslehre": "wisdom instruction",
        "Klagelied": "lamentation",
        "Hymne": "hymn", "Lobpreis": "praise",
        "Zauber": "magic", "Zauberspruch": "magical spell",
        "Amulett": "amulet", "Schutz": "protection",
    }

    # Build lowercase lookup for case-insensitive matching
    _STATIC_LOWER: dict[str, str] = {k.lower(): v for k, v in STATIC_BRIDGE.items()}

    def __init__(self, local_llm_url: str | None = None):
        self._local_url = local_llm_url or os.environ.get("LOCAL_LLM_URL")

    def bridge_glosses(
        self, german_glosses: dict[str, dict[str, int]]
    ) -> dict[str, dict[str, float]]:
        """For lemmas with German glosses, translate to English.

        1. First pass: apply STATIC_BRIDGE for exact matches
        2. Second pass (if LLM available): batch remaining to LLM

        Return {lemma_id: {english_gloss: confidence_score}}.
        """
        result: dict[str, dict[str, float]] = {}

        # Collect all unique German terms across all lemmas
        all_de_terms: set[str] = set()
        for glosses in german_glosses.values():
            all_de_terms.update(glosses.keys())

        # Phase 1: static bridge
        static_map = self._bridge_static(all_de_terms)

        # Phase 2: LLM for remaining
        remaining = [t for t in all_de_terms if t.lower() not in self._STATIC_LOWER]
        llm_map: dict[str, str] = {}
        if remaining and self._local_url:
            try:
                llm_map = self._bridge_llm(remaining)
            except Exception:
                logger.warning("LLM bridging failed, using static-only", exc_info=True)

        # Merge static + LLM into combined map
        combined: dict[str, str] = {}
        combined.update(static_map)
        combined.update(llm_map)

        # Apply to each lemma
        for lemma_id, glosses in german_glosses.items():
            en_scores: dict[str, float] = {}
            total = sum(glosses.values()) or 1
            for de_term, freq in glosses.items():
                en = combined.get(de_term.lower()) or combined.get(de_term)
                if en:
                    # Confidence based on frequency proportion + source
                    source_bonus = 1.0 if de_term.lower() in self._STATIC_LOWER else 0.8
                    score = (freq / total) * source_bonus
                    # Keep highest score per English term
                    if en not in en_scores or score > en_scores[en]:
                        en_scores[en] = round(score, 4)
            if en_scores:
                result[lemma_id] = en_scores

        logger.info(
            "Bridged %d/%d lemmas (static: %d terms, LLM: %d terms)",
            len(result), len(german_glosses), len(static_map), len(llm_map),
        )
        return result

    def _bridge_static(self, german_terms: set[str]) -> dict[str, str]:
        """Look up terms in STATIC_BRIDGE. Case-insensitive matching."""
        result: dict[str, str] = {}
        for term in german_terms:
            en = self._STATIC_LOWER.get(term.lower())
            if en:
                result[term.lower()] = en
        return result

    def _bridge_llm(
        self, german_terms: list[str], batch_size: int = 50
    ) -> dict[str, str]:
        """Send batches to local LLM for translation.

        Prompt: Translate German Egyptological terms to English, one per line.
        Format: N. German = English
        Uses positional matching: input term N → output line N.
        """
        import httpx

        result: dict[str, str] = {}

        for i in range(0, len(german_terms), batch_size):
            batch = german_terms[i : i + batch_size]
            # Number the terms so we can match by position
            numbered = "\n".join(f"{j+1}. {t}" for j, t in enumerate(batch))
            prompt = (
                "Translate these German Egyptological terms to English. "
                "One per line, keep the numbering. Format: N. German = English\n\n"
                f"{numbered}"
            )

            try:
                resp = httpx.post(
                    f"{self._local_url}/v1/chat/completions",
                    json={
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": batch_size * 60,
                    },
                    timeout=120.0,
                )
                resp.raise_for_status()
                msg = resp.json()["choices"][0]["message"]
                # Some models put output in reasoning_content (e.g. Gemma 4)
                content = msg.get("content") or msg.get("reasoning_content") or ""

                # Parse response: try positional matching first, then text matching
                parsed_lines = []
                for line in content.strip().splitlines():
                    if "=" not in line:
                        continue
                    parts = line.split("=", 1)
                    en = parts[1].strip().strip('"').strip("'")
                    if not en:
                        continue
                    # Try to extract line number
                    left = parts[0].strip()
                    import re
                    num_match = re.match(r"^(\d+)\.?\s*(.*)$", left)
                    if num_match:
                        idx = int(num_match.group(1)) - 1
                        if 0 <= idx < len(batch):
                            # Positional match — use original input term as key
                            result[batch[idx].lower()] = en
                            continue
                    # Fallback: text match
                    de = left.lower().strip()
                    if de:
                        result[de] = en

            except Exception:
                logger.warning(
                    "LLM batch %d–%d failed", i, i + len(batch), exc_info=True
                )

        logger.info("LLM bridged %d terms", len(result))
        return result
