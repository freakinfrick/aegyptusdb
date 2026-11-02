"""Rosetta Translator — witness-grounded translation engine."""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

from rosetta.witness.dossier import WitnessDossier

logger = logging.getLogger(__name__)

MODEL_ID_ANTHROPIC = "claude-sonnet-4-20250514"
MODEL_ID_LOCAL = "gemma-4-26B-A4B-it-UD-Q4_K_M.gguf"

ROSETTA_SYSTEM_PROMPT = """You are an expert Egyptologist producing English translations from multilingual evidence. You are given:
- The Egyptian transliteration
- Token-level English and German glosses from the Thoth Lexicon
- A German scholarly translation of the same text (if available)
- Similar sentences already translated into English (parallel examples)

Your task: produce a fluent, accurate English translation grounded in this evidence. Where the German translation is available, it should be your primary guide — translate the meaning of the German into natural English, using the token glosses to verify individual word meanings. Where only token glosses are available, compose the translation from the word-level meanings using the parallel examples as style guides.

Output format:
1. A single-paragraph English translation
2. Brief notes on significant uncertainties
3. Confidence: HIGH / MEDIUM / LOW"""

# Map dossier pre_confidence to tier labels
_CONFIDENCE_TO_TIER = {
    "high": "T1",
    "medium": "T2",
    "low": "T3",
}


class RosettaTranslator:
    """Produce English translations from WitnessDossiers."""

    def __init__(
        self,
        backend: str = "local",
        local_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self._backend = backend
        self._local_url = local_url or os.environ.get("LOCAL_LLM_URL")
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = None
        self._model = model or {
            "local": MODEL_ID_LOCAL,
            "anthropic": MODEL_ID_ANTHROPIC,
        }.get(backend, MODEL_ID_LOCAL)

        logger.info(
            "RosettaTranslator: backend=%s, model=%s", self._backend, self._model
        )

    def _get_client(self):
        """Lazy-init the Anthropic client."""
        if self._client is None and self._backend == "anthropic":
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def translate_with_witnesses(self, dossier: WitnessDossier):
        """Build grounded prompt from dossier, call LLM, parse response.

        Returns a TranslationResult from processing.draft_translation.service.
        """
        from processing.draft_translation.service import TranslationResult

        user_msg = self.build_witness_prompt(dossier)
        tier = _CONFIDENCE_TO_TIER.get(dossier.pre_confidence, "T3")

        try:
            if self._backend == "local":
                raw_text, call_meta = self._call_local(ROSETTA_SYSTEM_PROMPT, user_msg)
            elif self._backend == "anthropic":
                raw_text, call_meta = self._call_anthropic(ROSETTA_SYSTEM_PROMPT, user_msg)
            else:
                return TranslationResult(
                    sentence_id=dossier.sentence_id,
                    canonical_id=dossier.canonical_id,
                    error=f"Unknown backend: {self._backend}",
                    model=self._model,
                    backend=self._backend,
                )
        except Exception as e:
            logger.error(
                "LLM call failed for sentence %d: %s", dossier.sentence_id, e
            )
            return TranslationResult(
                sentence_id=dossier.sentence_id,
                canonical_id=dossier.canonical_id,
                error=str(e),
                model=self._model,
                backend=self._backend,
            )

        translation, notes, confidence_llm = self._parse_response(raw_text)

        calibrated = self._calibrate_confidence(
            confidence_llm, dossier.token_coverage, dossier.has_german,
            len(dossier.parallel_examples),
        )

        witnesses_used = []
        if dossier.has_german:
            witnesses_used.append("german_translation")
        if dossier.german_interlinear:
            witnesses_used.append("german_interlinear")
        if dossier.token_witnesses:
            witnesses_used.append("token_glosses")
        if dossier.parallel_examples:
            witnesses_used.append("parallel_examples")

        rosetta_meta = {
            "source": "ml_draft",
            "model": self._model,
            "tier": tier,
            "confidence": calibrated.lower() if calibrated else "low",
            "confidence_llm": confidence_llm,
            "witnesses_used": witnesses_used,
            "parallel_ids": [p.sentence_id for p in dossier.parallel_examples],
            "needs_review": True,
            "translated_at": datetime.now(timezone.utc).isoformat(),
        }

        meta = dict(call_meta)
        meta["_rosetta"] = rosetta_meta

        return TranslationResult(
            sentence_id=dossier.sentence_id,
            canonical_id=dossier.canonical_id,
            translation_en=translation,
            notes=notes,
            confidence_llm=confidence_llm,
            model=self._model,
            backend=self._backend,
            metadata=meta,
        )

    def build_witness_prompt(self, dossier: WitnessDossier) -> str:
        """Format WitnessDossier into the user message for the LLM."""
        parts = [f"**Transliteration:** {dossier.transliteration}"]

        if dossier.german_translation:
            parts.append(f"\n**German translation:** {dossier.german_translation}")

        if dossier.token_witnesses:
            parts.append(f"\n**Token glosses:**\n{dossier.format_token_glosses()}")

        if dossier.german_interlinear:
            parts.append(f"\n**German interlinear:** {dossier.german_interlinear}")

        if dossier.parallel_examples:
            parts.append(
                f"\n**Similar translated sentences:**\n{dossier.format_parallels()}"
            )

        context_parts = []
        if dossier.period:
            context_parts.append(f"Period: {dossier.period}")
        if dossier.text_type:
            context_parts.append(f"Type: {dossier.text_type}")
        if dossier.source:
            context_parts.append(f"Source: {dossier.source}")
        if context_parts:
            parts.append(f"\n**Context:** {', '.join(context_parts)}")

        parts.append(
            "\nProduce: English translation, notes, confidence (HIGH/MEDIUM/LOW)."
        )

        return "\n".join(parts)

    def _call_local(self, system: str, user_msg: str) -> tuple[str, dict]:
        """Call local llama-server. Return (raw_text, metadata)."""
        import httpx

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ]
        body = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.3,
            "max_completion_tokens": 1024,
        }

        r = httpx.post(
            f"{self._local_url}/v1/chat/completions",
            json=body,
            timeout=httpx.Timeout(180.0, connect=5.0),
        )
        r.raise_for_status()
        data = r.json()

        msg = data["choices"][0]["message"]
        raw_text = msg.get("content", "")
        # Strip <think>...</think> reasoning blocks
        raw_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()

        usage = data.get("usage", {})
        timings = data.get("timings", {})
        meta = {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "generation_tps": round(timings.get("predicted_per_second", 0), 1)
            if timings
            else None,
            "generation_time_s": round(timings.get("predicted_ms", 0) / 1000, 2)
            if timings
            else None,
            "stop_reason": data["choices"][0].get("finish_reason"),
        }
        return raw_text, meta

    def _call_anthropic(self, system: str, user_msg: str) -> tuple[str, dict]:
        """Call Anthropic Claude API. Return (raw_text, metadata)."""
        client = self._get_client()
        response = client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )

        raw_text = response.content[0].text
        meta = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "stop_reason": response.stop_reason,
        }
        return raw_text, meta

    def _parse_response(self, raw: str) -> tuple[str, Optional[str], Optional[str]]:
        """Parse LLM response into (translation, notes, confidence).

        Same logic as DraftTranslationService._parse_response.
        """
        lines = raw.strip().split("\n")
        translation_lines: list[str] = []
        notes_lines: list[str] = []
        confidence = None
        section = "translation"

        for line in lines:
            stripped = line.strip()
            lower = stripped.lower()

            conf_match = re.search(r"\b(HIGH|MEDIUM|LOW)\b", stripped)
            if "confidence" in lower and conf_match:
                confidence = conf_match.group(1)
                continue

            if lower.startswith("note") or lower.startswith("**note"):
                section = "notes"
                after_colon = stripped.split(":", 1)
                if len(after_colon) > 1 and after_colon[1].strip():
                    notes_lines.append(after_colon[1].strip())
                continue

            if section == "translation":
                if stripped:
                    translation_lines.append(stripped)
            else:
                if stripped:
                    notes_lines.append(stripped)

        translation = " ".join(translation_lines).strip()
        translation = re.sub(r"^#+\s*Translation\s*", "", translation)
        translation = re.sub(r"\*\*Translation:?\*\*\s*", "", translation)
        translation = re.sub(r"\*\*", "", translation)
        translation = translation.strip()

        notes = " ".join(notes_lines).strip() if notes_lines else None

        # Fallback confidence extraction
        if not confidence and notes:
            conf_fb = re.search(r"(?i)\bconfidence\b.*?\b(HIGH|MEDIUM|LOW)\b", notes)
            if conf_fb:
                confidence = conf_fb.group(1)
        if not confidence:
            conf_fb = re.search(r"(?i)\bconfidence\b.*?\b(HIGH|MEDIUM|LOW)\b", translation)
            if conf_fb:
                confidence = conf_fb.group(1)

        return translation, notes, confidence

    @staticmethod
    def _calibrate_confidence(
        llm_confidence: Optional[str],
        token_coverage: float,
        has_german: bool,
        parallel_count: int,
    ) -> str:
        """Calibrate LLM-reported confidence against evidence quality."""
        conf = (llm_confidence or "LOW").upper()

        if conf == "HIGH":
            if token_coverage < 0.5:
                conf = "MEDIUM"
            elif not has_german and parallel_count == 0:
                conf = "MEDIUM"
        elif conf == "MEDIUM":
            if token_coverage < 0.3:
                conf = "LOW"

        return conf
