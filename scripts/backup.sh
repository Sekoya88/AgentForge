#!/usr/bin/env bash
# scripts/backup.sh — dump Postgres, compress, keep 7 days
# Usage: ./scripts/backup.sh [backup_dir]
# Cron: 0 3 * * * /home/deploy/agentforge/scripts/backup.sh >> /var/log/agentforge-backup.log 2>&1

set -euo pipefail

BACKUP_DIR="${1:-/var/backups/agentforge}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILE="${BACKUP_DIR}/agentforge_${TIMESTAMP}.sql.gz"
TMPFILE="${FILE}.tmp"
KEEP_DAYS=7

mkdir -p "$BACKUP_DIR" || { echo "[$(date)] ERROR: Cannot create backup dir: $BACKUP_DIR" >&2; exit 1; }

# Load env vars if .env.prod exists next to the script's parent directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env.prod"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a && source "$ENV_FILE" && set +a
fi

POSTGRES_USER="${POSTGRES_USER:-forge}"
POSTGRES_DB="${POSTGRES_DB:-agentforge}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"

echo "[$(date)] Starting backup → ${FILE}"

docker compose -f "${SCRIPT_DIR}/../docker-compose.prod.yml" exec -T \
  -e PGPASSWORD="$POSTGRES_PASSWORD" db \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$TMPFILE"

# Guard against empty/corrupt backup (pg_dump failure can produce 0-byte output with exit 0)
if [[ ! -s "$TMPFILE" ]]; then
  rm -f "$TMPFILE"
  echo "[$(date)] ERROR: pg_dump produced empty output — backup aborted" >&2
  exit 1
fi

mv "$TMPFILE" "$FILE"
echo "[$(date)] Backup complete: $(du -sh "$FILE" | cut -f1)"

# Prune backups older than KEEP_DAYS (note: -mtime +7 = strictly older than 7×24h, day-7 backups are kept)
find "$BACKUP_DIR" -name "agentforge_*.sql.gz" -mtime "+${KEEP_DAYS}" -delete
echo "[$(date)] Pruned backups older than ${KEEP_DAYS} days"
