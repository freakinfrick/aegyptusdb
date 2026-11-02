"""JVM subprocess wrapper for TranslitModels Java tools.

Wraps the NeedlemanWunsch alignment JAR for aligning MdC encodings
with transliteration text. This is used during model TRAINING, not
inference -- the models themselves are JSON and loaded directly in Python.

The NeedlemanWunsch aligner is useful for:
- Aligning new parallel corpora (MdC + transliteration) for model expansion
- Quality-checking OCR output against known encodings

If Java is not available, all operations gracefully fall back to pass-through.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

JAVA_AVAILABLE = shutil.which("java") is not None
DEFAULT_JAR_DIR = Path(__file__).resolve().parents[2] / "data" / "upstream" / "translit_models" / "jar"


@dataclass
class AlignmentResult:
    """Result of NeedlemanWunsch alignment."""

    aligned_mdc: list[str]
    aligned_translit: list[str]
    success: bool
    error: str | None = None

    @property
    def pairs(self) -> list[tuple[str, str]]:
        """Return aligned (mdc, transliteration) pairs."""
        return list(zip(self.aligned_mdc, self.aligned_translit))


class NeedlemanWunschWrapper:
    """Wraps the MaReTENeedlemanWunsch.jar for sequence alignment.

    The JAR takes file-based input/output:
    - src file: MdC lines (words separated by _)
    - tgt file: Transliteration lines (words separated by _)
    - vocabulary files (tab-separated mdc<TAB>transliteration)

    Usage:
        wrapper = NeedlemanWunschWrapper()
        if wrapper.available:
            result = wrapper.align_lines(mdc_lines, translit_lines, vocab_file)
    """

    def __init__(self, jar_dir: str | Path | None = None):
        self.jar_dir = Path(jar_dir) if jar_dir else DEFAULT_JAR_DIR
        self.jar_path = self.jar_dir / "MaReTENeedlemanWunsch.jar"
        self._java_path = shutil.which("java")

    @property
    def available(self) -> bool:
        """Check if Java and the JAR are available."""
        return bool(self._java_path and self.jar_path.exists())

    def align_lines(
        self,
        mdc_lines: list[str],
        translit_lines: list[str],
        vocab_paths: list[str | Path] | None = None,
        timeout: int = 300,
    ) -> AlignmentResult:
        """Align MdC hieroglyph lines with transliteration lines via Needleman-Wunsch."""
        if not self.available:
            logger.warning(
                "NeedlemanWunsch alignment unavailable (java=%s, jar=%s). Passing through unchanged.",
                bool(self._java_path), self.jar_path.exists(),
            )
            return AlignmentResult(
                aligned_mdc=mdc_lines,
                aligned_translit=translit_lines,
                success=False,
                error="Java or JAR not available",
            )

        if len(mdc_lines) != len(translit_lines):
            return AlignmentResult(
                aligned_mdc=mdc_lines,
                aligned_translit=translit_lines,
                success=False,
                error=f"Line count mismatch: {len(mdc_lines)} MdC vs {len(translit_lines)} translit",
            )

        # Use default vocab files if none provided
        if vocab_paths is None:
            wordlists_dir = self.jar_dir.parent / "Output" / "WordLists"
            vocab_paths = [
                p for p in wordlists_dir.glob("*")
                if p.is_file() and p.name != "README.md"
            ]

        if not vocab_paths:
            return AlignmentResult(
                aligned_mdc=mdc_lines,
                aligned_translit=translit_lines,
                success=False,
                error="No vocabulary files available for alignment",
            )

        return self._run_alignment(mdc_lines, translit_lines, vocab_paths, timeout)

    def _run_alignment(
        self,
        mdc_lines: list[str],
        translit_lines: list[str],
        vocab_paths: list[str | Path],
        timeout: int,
    ) -> AlignmentResult:
        """Execute the JAR in a subprocess with temp files."""
        with tempfile.TemporaryDirectory(prefix="marete_") as tmpdir:
            tmpdir = Path(tmpdir)

            # Write input files
            src_file = tmpdir / "src_input"
            tgt_file = tmpdir / "tgt_input"
            src_file.write_text("\n".join(mdc_lines) + "\n")
            tgt_file.write_text("\n".join(translit_lines) + "\n")

            # Copy ignore.txt if it exists
            ignore_src = self.jar_dir.parent / "AccessoryFiles" / "ignore.txt"
            if ignore_src.exists():
                (tmpdir / "ignore.txt").write_text(ignore_src.read_text())

            # Build vocab argument
            vocab_str = ",".join(str(Path(v).resolve()) for v in vocab_paths)

            cmd = [
                self._java_path, "-jar", str(self.jar_path),
                str(src_file), str(tgt_file),
                vocab_str, "output",
            ]

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True, text=True,
                    timeout=timeout,
                    cwd=str(tmpdir),
                )

                if proc.returncode != 0:
                    logger.error("NeedlemanWunsch failed: %s", proc.stderr)
                    return AlignmentResult(
                        aligned_mdc=mdc_lines,
                        aligned_translit=translit_lines,
                        success=False,
                        error=f"JAR exited with code {proc.returncode}: {proc.stderr[:500]}",
                    )

                # Read output
                output_file = tmpdir / "aligned_output"
                if not output_file.exists():
                    return AlignmentResult(
                        aligned_mdc=mdc_lines,
                        aligned_translit=translit_lines,
                        success=False,
                        error="Alignment output file not created",
                    )

                return self._parse_output(output_file.read_text())

            except subprocess.TimeoutExpired:
                return AlignmentResult(
                    aligned_mdc=mdc_lines,
                    aligned_translit=translit_lines,
                    success=False,
                    error=f"Alignment timed out after {timeout}s",
                )
            except Exception as e:
                return AlignmentResult(
                    aligned_mdc=mdc_lines,
                    aligned_translit=translit_lines,
                    success=False,
                    error=str(e),
                )

    def _parse_output(self, output_text: str) -> AlignmentResult:
        """Parse the aligned output file.

        Format: alternating lines of aligned MdC and transliteration,
        separated by blank lines.
        """
        lines = output_text.strip().split("\n")
        aligned_mdc = []
        aligned_translit = []

        i = 0
        while i < len(lines):
            if lines[i].strip():
                aligned_mdc.append(lines[i].strip())
                if i + 1 < len(lines):
                    aligned_translit.append(lines[i + 1].strip())
                i += 3  # Skip blank line separator
            else:
                i += 1

        return AlignmentResult(
            aligned_mdc=aligned_mdc,
            aligned_translit=aligned_translit,
            success=True,
        )

    def check_health(self) -> dict:
        """Check if the JVM wrapper is operational."""
        status = {
            "java_available": bool(self._java_path),
            "java_path": self._java_path,
            "jar_exists": self.jar_path.exists(),
            "jar_path": str(self.jar_path),
            "operational": self.available,
        }

        if self._java_path:
            try:
                proc = subprocess.run(
                    [self._java_path, "-version"],
                    capture_output=True, text=True, timeout=10,
                )
                status["java_version"] = proc.stderr.strip().split("\n")[0]
            except Exception as e:
                status["java_version_error"] = str(e)

        return status
