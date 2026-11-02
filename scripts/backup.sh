#!/usr/bin/env bash
# backup.sh -- pg_dump wrapper for Aegyptus database.
#
# Produces a compressed, date-stamped backup file.
#
# Usage:
#   ./scripts/backup.sh                     # Default: ./backups/aegyptus_YYYY-MM-DD.sql.gz
#   ./scripts/backup.sh /path/to/backups    # Custom output directory
#
# Environment:
#   PGHOST     (default: localhost)
#   PGPORT     (default: 5434)
#   PGUSER     (default: aegyptus)
#   PGPASSWORD (default: dev)
#   PGDATABASE (default: aegyptus)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

BACKUP_DIR="${1:-$PROJECT_DIR/backups}"
DATE=$(date +%Y-%m-%d_%H%M%S)
FILENAME="aegyptus_${DATE}.sql.gz"

export PGHOST="${PGHOST:-localhost}"
export PGPORT="${PGPORT:-5434}"
export PGUSER="${PGUSER:-aegyptus}"
export PGPASSWORD="${PGPASSWORD:-dev}"
export PGDATABASE="${PGDATABASE:-aegyptus}"

mkdir -p "$BACKUP_DIR"

echo "Backing up $PGDATABASE@$PGHOST:$PGPORT..."
pg_dump --format=plain --no-owner --no-acl \
    | gzip > "$BACKUP_DIR/$FILENAME"

SIZE=$(du -sh "$BACKUP_DIR/$FILENAME" | cut -f1)
echo "Backup complete: $BACKUP_DIR/$FILENAME ($SIZE)"

# Clean up backups older than 30 days
DELETED=$(find "$BACKUP_DIR" -name "aegyptus_*.sql.gz" -mtime +30 -delete -print | wc -l)
if [ "$DELETED" -gt 0 ]; then
    echo "Cleaned up $DELETED backup(s) older than 30 days"
fi
