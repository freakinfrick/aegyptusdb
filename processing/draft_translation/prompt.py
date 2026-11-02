"""Prompt templates for Egyptological draft translation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

SYSTEM_PROMPT = """\
You are an expert Egyptologist specializing in the translation of ancient Egyptian texts. \
You produce scholarly draft translations from transliteration with lemma annotations.

Guidelines:
- Translate into clear, accurate English
- Preserve Egyptian proper nouns (divine names, place names, personal names) in their conventional Egyptological forms
- Mark uncertain readings with [?] and lacunae with [...]
- Where a word is ambiguous, choose the most contextually appropriate meaning
- For formulaic phrases (offering formulas, royal titulary, etc.), use standard Egyptological translations
- Note significant grammatical constructions (e.g., sdm.f forms, relative forms, stative)
- If the text is fragmentary, indicate what can and cannot be recovered

Output format:
1. A single-paragraph English translation
2. A brief note on any significant uncertainties or alternative readings
3. A confidence assessment: HIGH (formulaic/well-attested), MEDIUM (reasonable interpretation), LOW (fragmentary/ambiguous)\
"""


@dataclass
class TranslationPrompt:
    """A structured prompt for LLM-based Egyptian translation."""

    transliteration: str
    token_glosses: list[str]
    pos_sequence: list[str]
    source_info: str
    canonical_id: Optional[str] = None

    def build_user_message(self) -> str:
        """Build the user message for the LLM API call."""
        lines = [
            "Translate the following ancient Egyptian sentence into English.",
            "",
            f"**Transliteration:** {self.transliteration}",
            "",
        ]

        if self.token_glosses:
            lines.append("**Token-level glosses (lemma meanings):**")
            for gloss in self.token_glosses:
                lines.append(f"  - {gloss}")
            lines.append("")

        if self.pos_sequence:
            pos_str = " ".join(self.pos_sequence)
            lines.append(f"**POS sequence:** {pos_str}")
            lines.append("")

        if self.source_info:
            lines.append(f"**Source context:** {self.source_info}")
            lines.append("")

        lines.append("Provide your translation, notes, and confidence assessment.")
        return "\n".join(lines)

    @classmethod
    def from_sentence(
        cls,
        transliteration: str,
        tokens: list[dict],
        lemma_lookup: callable,
        canonical_id: Optional[str] = None,
        source: Optional[str] = None,
    ) -> TranslationPrompt:
        """Build a prompt from token data. lemma_lookup(lemma_id) → meaning string or None."""
        glosses = []
        pos_seq = []

        for tok in tokens:
            lemma_id = tok.get("lemmaID") or tok.get("lemma_id")
            written = tok.get("written_form") or tok.get("mdc") or "?"
            pos = tok.get("pos") or tok.get("upos") or "UNK"
            pos_seq.append(pos)

            if lemma_id:
                meaning = lemma_lookup(str(lemma_id))
                if meaning:
                    glosses.append(f"{written} (lemma {lemma_id}): {meaning}")
                else:
                    lemma_form = tok.get("lemma_form", "")
                    glosses.append(f"{written} (lemma {lemma_id}): {lemma_form or '?'}")
            else:
                # Lacuna or unlemmatized token
                glosses.append(f"{written}: [unlemmatized]")

        source_info = f"Source: {source or 'unknown'}"
        if canonical_id:
            source_info += f", Text ID: {canonical_id}"

        return cls(
            transliteration=transliteration,
            token_glosses=glosses,
            pos_sequence=pos_seq,
            source_info=source_info,
            canonical_id=canonical_id,
        )


def format_dry_run(prompt: TranslationPrompt) -> str:
    """Format what WOULD be sent to the API, for dry-run mode."""
    lines = [
        "=" * 60,
        "DRY RUN - Draft Translation Request",
        "=" * 60,
        "",
        "--- SYSTEM PROMPT ---",
        SYSTEM_PROMPT,
        "",
        "--- USER MESSAGE ---",
        prompt.build_user_message(),
        "",
        "=" * 60,
        "No API call made (dry-run mode).",
        "To enable live translation, either:",
        "  - Start llama-server (auto-detected at localhost:8012)",
        "  - Set LOCAL_LLM_URL=http://host:port",
        "  - Set ANTHROPIC_API_KEY=sk-ant-...",
        "=" * 60,
    ]
    return "\n".join(lines)
