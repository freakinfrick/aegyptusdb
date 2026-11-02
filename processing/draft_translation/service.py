"""Draft translation service using Claude API or local llama-server.

Produces English translations of Egyptian sentences with appropriate
ml_draft/low/needs_review tagging.

Backend priority:
  1. LOCAL_LLM_URL set  → local llama-server (OpenAI-compatible)
  2. ANTHROPIC_API_KEY set → Anthropic Claude API
  3. Neither → dry-run mode
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from core.models import RepresentationLayer, Sentence, SessionLocal

from .lemma_dict import LemmaDictionary
from .prompt import SYSTEM_PROMPT, TranslationPrompt, format_dry_run

logger = logging.getLogger(__name__)

MODEL_ID_ANTHROPIC = "claude-sonnet-4-20250514"
MODEL_ID_LOCAL = "gemma-4-26B-A4B-it-UD-Q4_K_M.gguf"
LOCAL_LLM_URL_DEFAULT = os.environ.get("LOCAL_LLM_URL", "http://127.0.0.1:8012")


@dataclass
class TranslationResult:
    """Result of a draft translation attempt."""

    sentence_id: int
    canonical_id: str
    translation_en: Optional[str] = None
    notes: Optional[str] = None
    confidence_llm: Optional[str] = None  # HIGH/MEDIUM/LOW from LLM
    dry_run: bool = False
    dry_run_prompt: Optional[str] = None
    error: Optional[str] = None
    model: str = MODEL_ID_LOCAL
    backend: str = "local"  # "local" | "anthropic" | "dry_run"
    metadata: dict = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return bool(self.translation_en) or self.dry_run

    @property
    def layer_metadata(self) -> dict:
        """Metadata dict for the representation layer record."""
        return {
            "source": "ml_draft",
            "model": self.model,
            "confidence": "low",
            "needs_review": True,
            "confidence_llm": self.confidence_llm,
            "notes": self.notes,
            "translated_at": datetime.now(timezone.utc).isoformat(),
        }


class DraftTranslationService:
    """Translates Egyptian sentences using local llama-server or Claude API.

    Backend priority (unless dry_run=True):
      1. LOCAL_LLM_URL env var or local_llm_url param → local llama-server
      2. ANTHROPIC_API_KEY env var or api_key param → Anthropic Claude API
      3. Neither → dry-run mode
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        local_llm_url: Optional[str] = None,
        model: Optional[str] = None,
        lemma_dict: Optional[LemmaDictionary] = None,
        dry_run: bool = False,
        use_rosetta: bool = False,
    ) -> None:
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._local_llm_url = local_llm_url or os.environ.get("LOCAL_LLM_URL")
        self._use_rosetta = use_rosetta
        self._client = None
        self._lemma_dict = lemma_dict

        if dry_run:
            self._backend = "dry_run"
            self._model = model or MODEL_ID_LOCAL
        elif self._local_llm_url:
            self._backend = "local"
            self._model = model or MODEL_ID_LOCAL
        elif self._api_key:
            self._backend = "anthropic"
            self._model = model or MODEL_ID_ANTHROPIC
        else:
            # No backend explicitly configured — fall through to dry-run.
            # Do NOT silently auto-detect a running llama-server on port 8012:
            # that server belongs to ytscribe's nightly pipeline and must not
            # be hijacked by Aegyptus translation jobs (causes 13h GPU hold).
            # To use the local 4090, pass --backend local / --local-url explicitly
            # or set LOCAL_LLM_URL in the environment.
            self._backend = "dry_run"
            self._model = model or MODEL_ID_LOCAL
            self._local_llm_url = None

        logger.info(
            "Draft translation service: backend=%s, model=%s",
            self._backend, self._model,
        )

    def _probe_local_llm(self) -> bool:
        """Quick health check on local llama-server."""
        import httpx
        try:
            r = httpx.get(f"{self._local_llm_url}/health", timeout=3.0)
            return r.status_code == 200
        except Exception:
            return False

    @property
    def is_dry_run(self) -> bool:
        return self._backend == "dry_run"

    @property
    def backend(self) -> str:
        return self._backend

    def _get_client(self):
        """Lazy-init the Anthropic client."""
        if self._client is None and self._backend == "anthropic":
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def _get_lemma_dict(self, session: Optional[Session] = None) -> LemmaDictionary:
        """Lazy-init the lemma dictionary."""
        if self._lemma_dict is None:
            logger.info("Building lemma dictionary from corpus (first call)...")
            self._lemma_dict = LemmaDictionary.build_from_corpus(session=session)
            logger.info("Lemma dictionary ready: %d entries", self._lemma_dict.size)
        return self._lemma_dict

    def translate_sentence(
        self,
        sentence: Sentence,
        session: Optional[Session] = None,
    ) -> TranslationResult:
        """Translate a single sentence."""
        if self._use_rosetta:
            try:
                from rosetta.witness.dossier import assemble_dossier
                from rosetta.engine.translator import RosettaTranslator
                dossier = assemble_dossier(sentence.id, session)
                translator = RosettaTranslator(backend=self._backend, local_url=self._local_llm_url)
                return translator.translate_with_witnesses(dossier)
            except ImportError:
                logger.warning("Rosetta not available, falling back to standard translation")
            except Exception as e:
                logger.warning("Rosetta translation failed, falling back: %s", e)

        if not sentence.transliteration:
            return TranslationResult(
                sentence_id=sentence.id,
                canonical_id=sentence.canonical_id,
                error="No transliteration available",
            )

        tokens = sentence.tokens or []
        ld = self._get_lemma_dict(session)

        prompt = TranslationPrompt.from_sentence(
            transliteration=sentence.transliteration,
            tokens=tokens,
            lemma_lookup=ld.lookup_meaning,
            canonical_id=sentence.canonical_id,
            source=sentence.source,
        )

        if self._backend == "dry_run":
            return TranslationResult(
                sentence_id=sentence.id,
                canonical_id=sentence.canonical_id,
                dry_run=True,
                dry_run_prompt=format_dry_run(prompt),
                model=self._model,
                backend="dry_run",
            )

        if self._backend == "local":
            return self._call_local(sentence.id, sentence.canonical_id, prompt)
        return self._call_anthropic(sentence.id, sentence.canonical_id, prompt)

    def _call_local(
        self, sentence_id: int, canonical_id: str, prompt: TranslationPrompt
    ) -> TranslationResult:
        """Call local llama-server (OpenAI-compatible endpoint)."""
        import httpx

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt.build_user_message()},
        ]
        body = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.3,
            "max_completion_tokens": 1024,
        }

        try:
            r = httpx.post(
                f"{self._local_llm_url}/v1/chat/completions",
                json=body,
                timeout=httpx.Timeout(180.0, connect=5.0),
            )
            r.raise_for_status()
            data = r.json()

            msg = data["choices"][0]["message"]
            raw_text = msg.get("content", "")
            # Strip any <think>...</think> reasoning blocks from Qwen
            raw_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()

            translation, notes, confidence = self._parse_response(raw_text)
            usage = data.get("usage", {})
            timings = data.get("timings", {})

            return TranslationResult(
                sentence_id=sentence_id,
                canonical_id=canonical_id,
                translation_en=translation,
                notes=notes,
                confidence_llm=confidence,
                model=self._model,
                backend="local",
                metadata={
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "generation_tps": round(timings.get("predicted_per_second", 0), 1) if timings else None,
                    "generation_time_s": round(timings.get("predicted_ms", 0) / 1000, 2) if timings else None,
                    "stop_reason": data["choices"][0].get("finish_reason"),
                },
            )
        except Exception as e:
            logger.error("Local LLM call failed for sentence %d: %s", sentence_id, e)
            return TranslationResult(
                sentence_id=sentence_id,
                canonical_id=canonical_id,
                error=str(e),
                model=self._model,
                backend="local",
            )

    def _call_anthropic(
        self, sentence_id: int, canonical_id: str, prompt: TranslationPrompt
    ) -> TranslationResult:
        """Call Anthropic Claude API."""
        client = self._get_client()
        try:
            response = client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt.build_user_message()}],
            )

            raw_text = response.content[0].text
            translation, notes, confidence = self._parse_response(raw_text)

            return TranslationResult(
                sentence_id=sentence_id,
                canonical_id=canonical_id,
                translation_en=translation,
                notes=notes,
                confidence_llm=confidence,
                model=self._model,
                backend="anthropic",
                metadata={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "stop_reason": response.stop_reason,
                },
            )
        except Exception as e:
            logger.error("Anthropic API call failed for sentence %d: %s", sentence_id, e)
            return TranslationResult(
                sentence_id=sentence_id,
                canonical_id=canonical_id,
                error=str(e),
                model=self._model,
                backend="anthropic",
            )

    def _parse_response(self, raw: str) -> tuple[str, Optional[str], Optional[str]]:
        """Parse LLM response into translation, notes, confidence."""
        lines = raw.strip().split("\n")
        translation_lines = []
        notes_lines = []
        confidence = None
        section = "translation"

        for line in lines:
            stripped = line.strip()
            lower = stripped.lower()

            # Detect confidence line
            conf_match = re.search(r"\b(HIGH|MEDIUM|LOW)\b", stripped)
            if "confidence" in lower and conf_match:
                confidence = conf_match.group(1)
                continue

            # Detect notes section
            if lower.startswith("note") or lower.startswith("**note"):
                section = "notes"
                # The note content may be on this line after the header
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
        # Clean markdown formatting from translation
        translation = re.sub(r"^#+\s*Translation\s*", "", translation)
        translation = re.sub(r"\*\*Translation:?\*\*\s*", "", translation)
        translation = re.sub(r"\*\*", "", translation)
        translation = translation.strip()

        notes = " ".join(notes_lines).strip() if notes_lines else None

        # Fallback: extract confidence from notes or translation if not found on its own line
        if not confidence and notes:
            conf_fb = re.search(r"(?i)\bconfidence\b.*?\b(HIGH|MEDIUM|LOW)\b", notes)
            if conf_fb:
                confidence = conf_fb.group(1)
        if not confidence:
            conf_fb = re.search(r"(?i)\bconfidence\b.*?\b(HIGH|MEDIUM|LOW)\b", translation)
            if conf_fb:
                confidence = conf_fb.group(1)

        return translation, notes, confidence

    def translate_batch(
        self,
        sentences: list[Sentence],
        session: Optional[Session] = None,
    ) -> list[TranslationResult]:
        """Translate a batch of sentences."""
        results = []
        for i, s in enumerate(sentences):
            result = self.translate_sentence(s, session=session)
            results.append(result)
            if (i + 1) % 10 == 0:
                logger.info("Translated %d/%d sentences", i + 1, len(sentences))
        return results

    def translate_batch_local(
        self,
        sentences: list[Sentence],
        session: Optional[Session] = None,
        batch_size: int = 20,
    ) -> list[TranslationResult]:
        """Translate sentences in batched LLM calls (N per request).

        Packs batch_size sentences into a single prompt with JSON output,
        dramatically reducing per-sentence overhead for fragments.
        """
        import httpx

        ld = self._get_lemma_dict(session)
        results = []

        for batch_start in range(0, len(sentences), batch_size):
            batch = sentences[batch_start:batch_start + batch_size]

            # Build compact batch prompt
            lines = []
            id_map = {}
            for s in batch:
                tokens = s.tokens or []
                glosses = []
                for tok in tokens:
                    lemma_id = tok.get("lemmaID") or tok.get("lemma_id")
                    written = tok.get("written_form") or tok.get("mdc") or "?"
                    if lemma_id:
                        meaning = ld.lookup_meaning(str(lemma_id))
                        glosses.append(f"{written}={meaning or '?'}")
                    else:
                        glosses.append(written)
                gloss_str = "; ".join(glosses) if glosses else ""
                lines.append(f"{s.id}|{s.transliteration or ''}|{gloss_str}")
                id_map[s.id] = s

            user_msg = (
                "Translate each ancient Egyptian sentence to English. "
                "For single-word entries, give the English meaning.\n"
                "Each line: ID|transliteration|glosses\n\n"
                + "\n".join(lines)
                + "\n\nOutput a JSON array:\n"
                '[{"id":12345,"en":"English translation","c":"HIGH"}]\n'
                "c = HIGH|MEDIUM|LOW.\n"
                "Output ONLY the JSON array, nothing else."
            )

            body = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": (
                        "You are an expert Egyptologist. Translate ancient Egyptian "
                        "transliterations to English using the provided token glosses. "
                        "Output only a JSON array."
                    )},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": 0.3,
                "max_completion_tokens": max(16384, batch_size * 800),
            }

            try:
                r = httpx.post(
                    f"{self._local_llm_url}/v1/chat/completions",
                    json=body,
                    timeout=httpx.Timeout(300.0, connect=5.0),
                )
                r.raise_for_status()
                data = r.json()
                raw_text = data["choices"][0]["message"].get("content", "")
                raw_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
                raw_text = re.sub(r"```json\s*", "", raw_text)
                raw_text = re.sub(r"```\s*", "", raw_text)

                timings = data.get("timings", {})
                tps = round(timings.get("predicted_per_second", 0), 1) if timings else None

                # Parse JSON array
                m = re.search(r"\[.*\]", raw_text, re.DOTALL)
                if m:
                    try:
                        items = json.loads(m.group())
                    except json.JSONDecodeError:
                        objects = re.findall(r"\{[^{}]+\}", m.group())
                        items = []
                        for o in objects:
                            try:
                                obj = json.loads(o)
                                if "id" in obj and "en" in obj:
                                    items.append(obj)
                            except json.JSONDecodeError:
                                pass

                    for item in items:
                        sid = item.get("id")
                        en = (item.get("en") or "").strip()
                        conf = item.get("c") or item.get("confidence") or "MEDIUM"
                        if sid and en and sid in id_map:
                            results.append(TranslationResult(
                                sentence_id=sid,
                                canonical_id=id_map[sid].canonical_id,
                                translation_en=en,
                                confidence_llm=conf,
                                model=self._model,
                                backend="local",
                                metadata={"generation_tps": tps, "batch_mode": True},
                            ))

                    logger.info(
                        "Batch %d-%d: %d/%d translated (%.1f tok/s)",
                        batch_start, batch_start + len(batch),
                        len([i for i in items if i.get("id") in id_map]),
                        len(batch), tps or 0,
                    )
                else:
                    finish = data["choices"][0].get("finish_reason", "?")
                    comp_tok = data.get("usage", {}).get("completion_tokens", 0)
                    logger.warning(
                        "Batch %d-%d: no JSON (finish=%s, comp_tok=%d, len=%d)",
                        batch_start, batch_start + len(batch), finish, comp_tok, len(raw_text),
                    )

            except Exception as e:
                logger.error("Batch %d-%d failed: %s", batch_start, batch_start + len(batch), e)

        return results

    def validate_translation(self, result: TranslationResult) -> tuple[bool, str]:
        """Sanity-check a translation before saving.

        Returns (is_valid, reason).
        """
        if not result.translation_en:
            return False, "empty translation"

        t = result.translation_en.strip()

        # Too short to be meaningful (relaxed for 1-2 token fragments)
        if len(t) < 2:
            return False, f"too short ({len(t)} chars)"

        # LLM echoed the transliteration back instead of translating
        if result.metadata.get("transliteration") and t == result.metadata.get("transliteration"):
            return False, "echoed transliteration"

        # Contains only markdown headers / formatting artifacts
        stripped = re.sub(r"[#*\-=\s]", "", t)
        if len(stripped) < 2:
            return False, "only formatting artifacts"

        # Absurdly long (LLM went off the rails)
        if len(t) > 5000:
            return False, f"too long ({len(t)} chars)"

        return True, "ok"

    def save_result(self, result: TranslationResult, session: Session) -> Optional[int]:
        """Save a successful translation to the sentence's translation JSONB.

        Writes the English translation directly onto the sentence row as
        translation->'en', alongside any existing translations (e.g. 'de').
        Also creates a representation layer for the first sentence per text.

        Never overwrites existing data:
        - Skips if sentence already has an 'en' translation
        - Validates translation quality before saving

        Returns 1 if saved, or None if nothing was saved.
        """
        if not result.success or result.dry_run or not result.translation_en:
            return None

        # Validate quality
        is_valid, reason = self.validate_translation(result)
        if not is_valid:
            logger.warning(
                "Rejected translation for sentence %d: %s", result.sentence_id, reason
            )
            return None

        # Update the sentence's translation JSONB with 'en' key
        sentence = session.get(Sentence, result.sentence_id)
        if not sentence:
            logger.warning("Sentence %d not found", result.sentence_id)
            return None

        existing_trans = sentence.translation or {}
        if "en" in existing_trans:
            logger.debug(
                "Skipping sentence %d: already has English translation",
                result.sentence_id,
            )
            return None

        from sqlalchemy.orm.attributes import flag_modified

        existing_trans["en"] = result.translation_en
        sentence.translation = dict(existing_trans)
        flag_modified(sentence, "translation")
        # Store metadata on the sentence's source_detail
        sentence_meta = dict(sentence.source_detail or {})
        sentence_meta["en_translation"] = result.layer_metadata
        sentence.source_detail = sentence_meta
        flag_modified(sentence, "source_detail")

        logger.info(
            "Saved English translation on sentence %d (%s)",
            result.sentence_id, result.canonical_id,
        )
        return 1

    def find_untranslated_sentences(
        self,
        session: Session,
        source: Optional[str] = None,
        limit: int = 100,
        min_tokens: int = 3,
    ) -> list[Sentence]:
        """Find sentences that have transliteration and tokens but no English translation.

        Targets sentences where translation is None or has no 'en' key.
        Requires at least min_tokens tokens (default 3) to skip tiny fragments.
        Orders by token count descending — longest sentences first.
        """
        from sqlalchemy import text as sa_text

        query = """
            SELECT s.id FROM sentences s
            WHERE s.transliteration IS NOT NULL
            AND s.tokens IS NOT NULL
            AND jsonb_array_length(s.tokens) >= :min_tokens
            AND (s.translation IS NULL OR NOT (s.translation ? 'en'))
        """
        params: dict = {"limit": limit, "min_tokens": min_tokens}
        if source:
            query += " AND s.source = :source"
            params["source"] = source
        query += " ORDER BY jsonb_array_length(s.tokens) ASC LIMIT :limit"

        ids = [row[0] for row in session.execute(sa_text(query), params).fetchall()]
        if not ids:
            return []

        return session.query(Sentence).filter(Sentence.id.in_(ids)).all()
