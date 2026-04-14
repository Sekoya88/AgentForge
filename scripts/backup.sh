#!/usr/bin/env bash
# scripts/backup.sh — dump Postgres, compress, keep 7 days
# Usage: ./scripts/backup.sh [backup_dir]
# Cron: 0 3 * * * /home/deploy/agentforge/scripts/backup.sh >> /var/log/agentforge-backup.log 2>&1

set -euo pipefail

BACKUP_DIR="${1:-/var/backups/agentforge}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILE="${BACKUP_DIR}/agentforge_${TIMESTAMP}.sql.gz"
KEEP_DAYS=7

mkdir -p "$BACKUP_DIR"

# Load env vars if .env.prod exists next to the script's parent directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env.prod"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a && source "$ENV_FILE" && set +a
fi

POSTGRES_USER="${POSTGRES_USER:-forge}"
POSTGRES_DB="${POSTGRES_DB:-agentforge}"

echo "[$(date)] Starting backup → ${FILE}"

docker compose -f "${SCRIPT_DIR}/../docker-compose.prod.yml" exec -T db \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$FILE"

echo "[$(date)] Backup complete: $(du -sh "$FILE" | cut -f1)"

# Remove backups older than KEEP_DAYS
find "$BACKUP_DIR" -name "agentforge_*.sql.gz" -mtime "+${KEEP_DAYS}" -delete
echo "[$(date)] Pruned backups older than ${KEEP_DAYS} days"
