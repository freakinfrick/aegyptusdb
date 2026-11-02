#!/usr/bin/env bash
# bootstrap.sh -- One command to go from fresh clone to ready-to-import.
#
# Usage: ./scripts/bootstrap.sh            (PYTHON=python3.11 ./scripts/bootstrap.sh
#                                            if python3 is older than 3.11)
#        then: source .venv/bin/activate && aegyptus import --source all
#
# Steps:
#   1. Create Python venv and install dependencies
#   2. Clone upstream repos into data/upstream/ (ORAEC, AES, AED-TEI, Coptic Scriptorium; ~4 GB)
#   3. Download Nederhof hierojax texts
#   4. Download RAMSES archive from Zenodo
#   5. Start Docker dev profile (Postgres + MinIO)
#   6. Run Alembic migrations
#   7. Print summary
#
# Fetched by the importers themselves: TLA (Hugging Face cache), papyri.info
# (clones idp.data), Trismegistos and Met (APIs). PhilologEg needs its JAR
# placed by hand (see docs/IMPORTERS.md).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="${DATA_DIR:-$PROJECT_DIR/data/upstream}"

cd "$PROJECT_DIR"

echo "=== Aegyptus Bootstrap ==="
echo "Project dir: $PROJECT_DIR"
echo "Data dir:    $DATA_DIR"
echo ""

# ── 1. Python venv ─────────────────────────────────────────────

PYTHON="${PYTHON:-python3}"
py_ok() { "$1" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; }
if ! py_ok "$PYTHON"; then
    echo "ERROR: Aegyptus needs Python 3.11+; '$PYTHON' is $("$PYTHON" -V 2>&1)."
    echo "       Re-run with a newer interpreter: PYTHON=python3.11 ./scripts/bootstrap.sh"
    exit 1
fi
# A venv left by an older interpreter would fail the install; rebuild it.
if [ -d ".venv" ] && ! py_ok .venv/bin/python; then
    echo "      Removing .venv built with $(.venv/bin/python -V 2>&1)"
    rm -rf .venv
fi

if [ ! -d ".venv" ]; then
    echo "[1/7] Creating Python virtual environment..."
    "$PYTHON" -m venv .venv
else
    echo "[1/7] Virtual environment already exists."
fi

source .venv/bin/activate
echo "      Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -e ".[dev]"

# ── 2. Clone upstream repos ────────────────────────────────────

echo "[2/7] Cloning upstream repositories..."
mkdir -p "$DATA_DIR"

clone_if_missing() {
    local repo_url="$1"
    local target_dir="$2"
    if [ -d "$target_dir" ]; then
        echo "      Already exists: $target_dir"
    else
        echo "      Cloning: $repo_url"
        git clone --depth 1 "$repo_url" "$target_dir"
    fi
}

clone_if_missing "https://github.com/oraec/corpus_raw_data.git" "$DATA_DIR/oraec_corpus_raw_data"
clone_if_missing "https://github.com/simondschweitzer/aes.git" "$DATA_DIR/aes"
clone_if_missing "https://github.com/oraec/formerly-mdc-now_unicode.git" "$DATA_DIR/oraec_unicode"
clone_if_missing "https://github.com/oraec/recommendations-encoding-hieroglyphs.git" "$DATA_DIR/oraec_encoding_recs"
clone_if_missing "https://github.com/simondschweitzer/aed-tei.git" "$DATA_DIR/aed_tei"
clone_if_missing "https://github.com/CopticScriptorium/corpora.git" "$DATA_DIR/coptic_scriptorium"

# ── 3. Download Nederhof hierojax texts ────────────────────────

echo "[3/7] Downloading Nederhof hierojax texts..."
NEDERHOF_DIR="$DATA_DIR/nederhof_hierojax"
if [ -d "$NEDERHOF_DIR" ]; then
    echo "      Already exists: $NEDERHOF_DIR"
else
    # The texts are the GitHub Pages files under docs/texts/ in nederhof/hierojax.
    HIEROJAX_TMP="$(mktemp -d)"
    git clone --depth 1 https://github.com/nederhof/hierojax.git "$HIEROJAX_TMP/hierojax"
    mkdir -p "$NEDERHOF_DIR"
    cp "$HIEROJAX_TMP"/hierojax/docs/texts/*.html "$NEDERHOF_DIR"/
    rm -rf "$HIEROJAX_TMP"
    echo "      $(ls "$NEDERHOF_DIR" | wc -l) texts in $NEDERHOF_DIR"
fi

# ── 4. Download RAMSES archive ─────────────────────────────────

echo "[4/7] Downloading RAMSES archive from Zenodo..."
RAMSES_DIR="$DATA_DIR/ramses"
if [ -d "$RAMSES_DIR" ]; then
    echo "      Already exists: $RAMSES_DIR"
else
    mkdir -p "$RAMSES_DIR"
    echo "      Fetching from Zenodo (record 4954597)..."
    # Only the corpus zip; the record's 106 MB network.h5 model is not needed.
    curl -fsSL "https://zenodo.org/records/4954597/files/ramses-trl_2021_05_29.zip?download=1" -o "$RAMSES_DIR/ramses.zip" \
        && unzip -q "$RAMSES_DIR/ramses.zip" -d "$RAMSES_DIR" \
        && rm "$RAMSES_DIR/ramses.zip" \
        || { rm -rf "$RAMSES_DIR"; echo "      WARNING: RAMSES download failed. Re-run bootstrap to retry."; }
fi

# Unicode's Unikemet sign properties (hieroglyph sign metadata).
mkdir -p "$DATA_DIR/unikemet"
[ -f "$DATA_DIR/unikemet/Unikemet.txt" ] || curl -sL \
    "https://www.unicode.org/Public/UCD/latest/ucd/Unikemet.txt" -o "$DATA_DIR/unikemet/Unikemet.txt" \
    || echo "      WARNING: Unikemet download failed. You can retry manually."

# ── 5. Start Docker dev profile ────────────────────────────────

echo "[5/7] Starting Docker dev profile (Postgres + MinIO)..."
docker compose --profile dev up -d

# Wait for Postgres to be ready
echo "      Waiting for Postgres..."
for i in $(seq 1 30); do
    if docker compose exec db pg_isready -U aegyptus -q 2>/dev/null; then
        echo "      Postgres is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "      WARNING: Postgres did not become ready in 30 seconds."
    fi
    sleep 1
done

# ── 6. Run Alembic migrations ──────────────────────────────────

echo "[6/7] Running Alembic migrations..."
alembic upgrade head

# ── 7. Summary ─────────────────────────────────────────────────

echo ""
echo "[7/7] Bootstrap complete!"
echo ""
echo "=== Summary ==="
echo "Upstream data:"
for d in "$DATA_DIR"/*/; do
    if [ -d "$d" ]; then
        count=$(find "$d" -type f 2>/dev/null | wc -l)
        echo "  $(basename "$d"): $count files"
    fi
done
echo ""
echo "Database: postgresql://aegyptus:dev@localhost:5434/aegyptus"
echo "MinIO:    http://localhost:9000 (console: http://localhost:9001)"
echo ""
echo "Next steps:"
echo "  source .venv/bin/activate"
echo "  aegyptus import --source all     # every importer, in dependency order (hours)"
echo "  aegyptus import --status --pretty"
echo ""
echo "Optional: place PhilologEg-0.5.14.jar in $DATA_DIR/ for the nederhof-philologeg importer."
