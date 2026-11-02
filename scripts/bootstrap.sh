#!/usr/bin/env bash
# bootstrap.sh -- One command to go from fresh clone to ready-to-import.
#
# Usage: ./scripts/bootstrap.sh
#
# Steps:
#   1. Create Python venv and install dependencies
#   2. Clone upstream repos into data/upstream/
#   3. Download Nederhof hierojax texts
#   4. Download TLA HF datasets
#   5. Download RAMSES archive from Zenodo
#   6. Start Docker dev profile (Postgres + MinIO)
#   7. Run Alembic migrations
#   8. Print summary

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

if [ ! -d ".venv" ]; then
    echo "[1/8] Creating Python virtual environment..."
    python3 -m venv .venv
else
    echo "[1/8] Virtual environment already exists."
fi

source .venv/bin/activate
echo "      Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -e ".[dev]"

# ── 2. Clone upstream repos ────────────────────────────────────

echo "[2/8] Cloning upstream repositories..."
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

# ── 3. Download Nederhof hierojax texts ────────────────────────

echo "[3/8] Downloading Nederhof hierojax texts..."
NEDERHOF_DIR="$DATA_DIR/nederhof_hierojax"
if [ -d "$NEDERHOF_DIR" ]; then
    echo "      Already exists: $NEDERHOF_DIR"
else
    mkdir -p "$NEDERHOF_DIR"
    echo "      Fetching from nederhof.github.io/hierojax/texts..."
    echo "      NOTE: Manual download may be required. Creating placeholder."
    echo "Download hierojax texts from https://nederhof.github.io/hierojax/texts" > "$NEDERHOF_DIR/README.txt"
fi

# ── 4. Download TLA HF datasets ───────────────────────────────

echo "[4/8] Downloading TLA Hugging Face datasets..."
python3 -c "
from huggingface_hub import snapshot_download
import os

data_dir = os.environ.get('DATA_DIR', './data/upstream')
hf_dir = os.path.join(data_dir, 'tla_hf')
os.makedirs(hf_dir, exist_ok=True)

datasets = [
    'thesaurus-linguae-aegyptiae/earlier-egyptian',
    'thesaurus-linguae-aegyptiae/late-egyptian',
    'thesaurus-linguae-aegyptiae/demotic',
]

for ds in datasets:
    name = ds.split('/')[-1]
    target = os.path.join(hf_dir, name)
    if os.path.exists(target):
        print(f'      Already exists: {target}')
    else:
        print(f'      Downloading: {ds}')
        snapshot_download(repo_id=ds, repo_type='dataset', local_dir=target)
print('      TLA HF download complete.')
" 2>&1 || echo "      WARNING: TLA HF download failed. You can retry manually."

# ── 5. Download RAMSES archive ─────────────────────────────────

echo "[5/8] Downloading RAMSES archive from Zenodo..."
RAMSES_DIR="$DATA_DIR/ramses"
if [ -d "$RAMSES_DIR" ]; then
    echo "      Already exists: $RAMSES_DIR"
else
    mkdir -p "$RAMSES_DIR"
    echo "      Fetching from Zenodo (record 4954597)..."
    curl -sL "https://zenodo.org/api/records/4954597/files-archive" -o "$RAMSES_DIR/ramses.zip" 2>/dev/null \
        && unzip -q "$RAMSES_DIR/ramses.zip" -d "$RAMSES_DIR" \
        && rm "$RAMSES_DIR/ramses.zip" \
        || echo "      WARNING: RAMSES download failed. You can retry manually."
fi

# Unicode's Unikemet sign properties (hieroglyph sign metadata).
mkdir -p "$DATA_DIR/unikemet"
[ -f "$DATA_DIR/unikemet/Unikemet.txt" ] || curl -sL \
    "https://www.unicode.org/Public/UCD/latest/ucd/Unikemet.txt" -o "$DATA_DIR/unikemet/Unikemet.txt" \
    || echo "      WARNING: Unikemet download failed. You can retry manually."

# ── 6. Start Docker dev profile ────────────────────────────────

echo "[6/8] Starting Docker dev profile (Postgres + MinIO)..."
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

# ── 7. Run Alembic migrations ──────────────────────────────────

echo "[7/8] Running Alembic migrations..."
alembic upgrade head

# ── 8. Summary ─────────────────────────────────────────────────

echo ""
echo "[8/8] Bootstrap complete!"
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
echo "  python -m aegyptus.importers.oraec   # Import ORAEC corpus"
echo "  python -m aegyptus.importers.aes     # Import AES sentences"
