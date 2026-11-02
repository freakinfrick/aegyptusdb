#!/usr/bin/env bash
# Photos of a bound book -> clean Markdown, one .md per source photo.
#
# Stages (each skips work already on disk, so re-running resumes):
#   1 heic   HEIC/JPG -> PNG            (pillow-heif; ImageMagick has no heic delegate here)
#   2 split  spread photo -> columns    (scripts/split_columns.py)
#   3 dewarp straighten bowed lines     (scripts/dewarp_columns.py)
#   4 ocr    docling backend per column (~35s/column, CPU)
#   5 join   concat columns per page    (filename order == reading order)
#   6 clean  llm-clean space repair     (needs a local OpenAI-compatible LLM server)
#
# Why this shape: scrambled reading order on book photos is a segmentation
# problem (two-page spread x two columns), not a geometry one -- so columns are
# cut BEFORE OCR. Dewarp is a small (~5px) correction that still matters,
# applied per column where the bow is nearly a pure vertical shift.
#
# Usage:
#   book_photo_ocr.sh IN_DIR [-o OUT_DIR] [--force-cols N] [--no-clean]
#                            [--only PAGE] [--stage N]
set -euo pipefail

SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PY:-$HOME/venv/bin/python}"
DOCLING="${DOCLING:-$HOME/.claude/skills/docling/docling_skill.py}"

IN=""; OUT=""; FORCE_COLS=0; CLEAN=1; ONLY=""; START_STAGE=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o|--outdir)     OUT="$2"; shift 2 ;;
    --force-cols)    FORCE_COLS="$2"; shift 2 ;;
    --no-clean)      CLEAN=0; shift ;;
    --only)          ONLY="$2"; shift 2 ;;   # single page stem, e.g. IMG_1541
    --stage)         START_STAGE="$2"; shift 2 ;;
    -h|--help)       sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *)               IN="$1"; shift ;;
  esac
done

[[ -n "$IN" && -d "$IN" ]] || { echo "usage: $(basename "$0") IN_DIR [-o OUT_DIR]" >&2; exit 1; }
IN="$(cd "$IN" && pwd)"
OUT="${OUT:-$IN}"
mkdir -p "$OUT"

for f in "$SCRIPTS/split_columns.py" "$SCRIPTS/dewarp_columns.py" "$DOCLING"; do
  [[ -f "$f" ]] || { echo "missing: $f" >&2; exit 1; }
done

glob() { ls "$@" 2>/dev/null || true; }   # empty instead of failing under -e

# 1 -- HEIC/JPG -> PNG
if (( START_STAGE <= 1 )); then
  echo "== 1/6 heic -> png"
  "$PY" - "$IN" <<'PYEOF'
import glob, os, sys
import pillow_heif
from PIL import Image
pillow_heif.register_heif_opener()
d = sys.argv[1]
for pat in ("*.HEIC", "*.heic", "*.JPG", "*.jpg", "*.jpeg"):
    for f in sorted(glob.glob(os.path.join(d, pat))):
        out = os.path.splitext(f)[0] + ".png"
        if os.path.exists(out):
            continue
        Image.open(f).save(out)
        print("  png:", os.path.basename(out))
PYEOF
fi

PNGS=()
while IFS= read -r f; do PNGS+=("$f"); done < <(glob "$IN"/*.png)
[[ -n "$ONLY" ]] && { PNGS=(); while IFS= read -r f; do PNGS+=("$f"); done < <(glob "$IN/$ONLY.png"); }
(( ${#PNGS[@]} )) || { echo "no PNGs in $IN" >&2; exit 1; }

# 2 -- columns
if (( START_STAGE <= 2 )); then
  echo "== 2/6 split columns"
  args=(--outdir "$OUT/cols")
  (( FORCE_COLS > 1 )) && args+=(--force-cols "$FORCE_COLS")
  "$PY" "$SCRIPTS/split_columns.py" "${PNGS[@]}" "${args[@]}"
fi

# 3 -- dewarp
if (( START_STAGE <= 3 )); then
  echo "== 3/6 dewarp columns"
  cols=(); while IFS= read -r f; do cols+=("$f"); done < <(glob "$OUT/cols"/*.png)
  (( ${#cols[@]} )) && "$PY" "$SCRIPTS/dewarp_columns.py" "${cols[@]}" --outdir "$OUT/cols_dw"
fi

# 4 -- OCR (slow; resumable)
if (( START_STAGE <= 4 )); then
  echo "== 4/6 ocr columns (docling backend)"
  mkdir -p "$OUT/colmd"
  n=0; total=$(glob "$OUT/cols_dw"/*.png | wc -l)
  for f in $(glob "$OUT/cols_dw"/*.png); do
    n=$((n+1)); b="$(basename "$f" .png)"
    if [[ -f "$OUT/colmd/$b.md" ]]; then echo "  skip $b ($n/$total)"; continue; fi
    echo "  ocr  $b ($n/$total)"
    python3 "$DOCLING" convert "$f" --backend docling --output "$OUT/colmd" >/dev/null 2>&1
  done
fi

# 5 -- join columns into one .md per page
if (( START_STAGE <= 5 )); then
  echo "== 5/6 join columns"
  mkdir -p "$OUT/md_raw"
  for p in "${PNGS[@]}"; do
    stem="$(basename "$p" .png)"
    parts=$(glob "$OUT/colmd/${stem}_c"*.md)
    [[ -n "$parts" ]] || continue
    : > "$OUT/md_raw/$stem.md"
    for c in $parts; do cat "$c" >> "$OUT/md_raw/$stem.md"; echo >> "$OUT/md_raw/$stem.md"; done
    echo "  page $stem"
  done
fi

# 6 -- LLM space repair
if (( START_STAGE <= 6 && CLEAN == 1 )); then
  echo "== 6/6 llm-clean"
  mkdir -p "$OUT/md_final"
  for f in $(glob "$OUT/md_raw"/*.md); do
    b="$(basename "$f")"
    [[ -f "$OUT/md_final/$b" ]] && { echo "  skip $b"; continue; }
    python3 "$DOCLING" llm-clean "$f" --output "$OUT/md_final/$b" 2>&1 | grep -E "done|error" || true
  done
  echo "done -> $OUT/md_final"
else
  echo "done -> $OUT/md_raw (clean skipped)"
fi
